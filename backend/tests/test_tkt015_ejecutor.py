"""TKT-015b · Ejecutor del análisis en otro proceso (fila B4): TC-52 a TC-62.

Las pruebas no usan `sleep`: esperan con `esperar_latidos` y `esperar_inactivo`, con tope de 30 s.
Cada prueba libera a los hijos bloqueados y cierra el ejecutor al terminar.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from sqlalchemy.orm import Session, sessionmaker
from structlog.testing import capture_logs

from cimenta.presupuesto.dominio.importacion import MotivoInterrupcion, error_de_interrupcion

if TYPE_CHECKING:
    from conftest import Conectar, DatosPresupuesto, LibroCatalogo

    from cimenta.presupuesto.infraestructura.ejecutor_analisis import EjecutorAnalisis
    from cimenta.presupuesto.infraestructura.trabajo_analisis import ResultadoAnalisis

TOPE = 30.0

type Trabajo = Callable[[uuid.UUID, bytes, Mapping[str, str]], ResultadoAnalisis]


@pytest.fixture
def fabrica_sesiones(motor_aplicacion) -> sessionmaker[Session]:
    return sessionmaker(bind=motor_aplicacion, expire_on_commit=False)


@dataclass
class Escenario:
    """Origen de bytes en memoria, ejecutores creados y rutas de liberación de la prueba."""

    fabrica: sessionmaker[Session]
    directorio: Path
    origen: dict[uuid.UUID, bytes] = field(default_factory=dict)
    ejecutores: list[EjecutorAnalisis] = field(default_factory=list)
    rutas: list[Path] = field(default_factory=list)

    def ruta(self, nombre: str = "liberar") -> Path:
        ruta = self.directorio / nombre
        self.rutas.append(ruta)
        return ruta

    def crear(
        self,
        *,
        leer_contenido: Callable[[uuid.UUID], bytes] | None = None,
        trabajo: Trabajo | None = None,
    ) -> EjecutorAnalisis:
        from cimenta.presupuesto.aplicacion.analisis_importacion import SeguimientoImportacion
        from cimenta.presupuesto.infraestructura.ejecutor_analisis import EjecutorAnalisis
        from herramientas.soporte_tkt015 import trabajo_de_prueba

        ejecutor = EjecutorAnalisis(
            seguimiento=SeguimientoImportacion(self.fabrica),
            leer_contenido=leer_contenido or self.origen.__getitem__,
            intervalo_latido=timedelta(milliseconds=200),
            trabajo=trabajo if trabajo is not None else trabajo_de_prueba,
        )
        self.ejecutores.append(ejecutor)
        return ejecutor

    def importacion(
        self,
        datos: DatosPresupuesto,
        contenido: bytes,
        *,
        estado: str = "RECIBIDO",
    ) -> uuid.UUID:
        archivo_id = uuid.uuid4()
        self.origen[archivo_id] = contenido
        return datos.importacion(archivo_id=archivo_id, estado=estado)


@pytest.fixture
def escenario(fabrica_sesiones: sessionmaker[Session], tmp_path: Path) -> Iterator[Escenario]:
    from herramientas.soporte_tkt015 import liberar

    actual = Escenario(fabrica=fabrica_sesiones, directorio=tmp_path)
    try:
        yield actual
    finally:
        for ruta in actual.rutas:
            if not ruta.exists():
                liberar(ruta)
        for ejecutor in actual.ejecutores:
            ejecutor.cerrar()


def _fila(conectar: Conectar, base: str, importacion_id: uuid.UUID) -> dict[str, Any]:
    with conectar("aplicacion", base) as conn:
        fila = conn.execute(
            "SELECT estado, progreso, latido, preparacion FROM importacion WHERE id = %s",
            (importacion_id,),
        ).fetchone()
    assert fila is not None
    estado, progreso, latido, preparacion = fila
    return {"estado": estado, "progreso": progreso, "latido": latido, "preparacion": preparacion}


def _errores(conectar: Conectar, base: str, importacion_id: uuid.UUID) -> list[tuple[Any, ...]]:
    with conectar("aplicacion", base) as conn:
        return conn.execute(
            "SELECT tipo, mensaje, hoja, fila, columna, valor_original "
            "FROM importacion_error WHERE importacion_id = %s ORDER BY mensaje",
            (importacion_id,),
        ).fetchall()


def _mensaje(motivo: MotivoInterrupcion) -> str:
    return error_de_interrupcion(motivo).mensaje


def _esperar_progreso(
    ejecutor: EjecutorAnalisis,
    leer: Callable[[], Any],
    minimo: Any,
) -> None:
    """Deja pasar latidos hasta que el avance del hijo llegue a la base (el arranque tarda)."""
    for _ in range(150):
        if leer() >= minimo:
            return
        assert ejecutor.esperar_latidos(1, TOPE)
    pytest.fail(f"el progreso no llegó a {minimo}")


def test_tkt015_analisis_en_otro_proceso(
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
    escenario: Escenario,
) -> None:
    """TC-52 · CA-12 — solicitar_analisis no espera al hijo, que corre en otro proceso."""
    from cimenta.presupuesto.aplicacion.analisis_importacion import solicitar_analisis
    from herramientas.soporte_tkt015 import liberar

    ruta = escenario.ruta()
    importacion_id = escenario.importacion(datos_presupuesto, f"bloquear:{ruta}".encode())
    ejecutor = escenario.crear()

    solicitar_analisis(escenario.fabrica, ejecutor, importacion_id)

    assert _fila(conectar, base_de_prueba, importacion_id)["estado"] == "ANALIZANDO"
    liberar(ruta)
    assert ejecutor.esperar_inactivo(TOPE)
    fila = _fila(conectar, base_de_prueba, importacion_id)
    assert fila["estado"] == "VALIDADO"
    assert fila["preparacion"]["pid"] != os.getpid()


def test_tkt015_dos_importaciones_en_serie(
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
    escenario: Escenario,
) -> None:
    """TC-53 · CA-12 — un solo trabajo a la vez: intervalos disjuntos y el mismo proceso."""
    from cimenta.presupuesto.aplicacion.analisis_importacion import solicitar_analisis

    primera = escenario.importacion(datos_presupuesto, b"anotar")
    segunda = escenario.importacion(datos_presupuesto, b"anotar")
    ejecutor = escenario.crear()

    solicitar_analisis(escenario.fabrica, ejecutor, primera)
    solicitar_analisis(escenario.fabrica, ejecutor, segunda)

    assert ejecutor.esperar_inactivo(TOPE)
    a = _fila(conectar, base_de_prueba, primera)
    b = _fila(conectar, base_de_prueba, segunda)
    assert a["estado"] == "VALIDADO"
    assert b["estado"] == "VALIDADO"
    pa, pb = a["preparacion"], b["preparacion"]
    assert pa["pid"] == pb["pid"]
    primero, segundo = sorted((pa, pb), key=lambda p: p["inicio"])
    assert primero["fin"] <= segundo["inicio"]


def test_hdu001_esc04_progreso_y_latido_mientras_analiza(
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
    escenario: Escenario,
) -> None:
    """TC-54 · CA-13 · HDU-001 esc. 4 — el progreso avanza y el latido se renueva."""
    from cimenta.presupuesto.aplicacion.analisis_importacion import solicitar_analisis
    from herramientas.soporte_tkt015 import liberar

    ruta = escenario.ruta()
    importacion_id = escenario.importacion(datos_presupuesto, f"avance:{ruta}".encode())
    ejecutor = escenario.crear()

    solicitar_analisis(escenario.fabrica, ejecutor, importacion_id)
    _esperar_progreso(
        ejecutor,
        lambda: _fila(conectar, base_de_prueba, importacion_id)["progreso"],
        Decimal("0.000001"),
    )
    primera = _fila(conectar, base_de_prueba, importacion_id)
    # Dos latidos: el primero podría haberse emitido antes de la consulta anterior.
    assert ejecutor.esperar_latidos(2, TOPE)
    segunda = _fila(conectar, base_de_prueba, importacion_id)

    assert primera["estado"] == "ANALIZANDO"
    assert segunda["estado"] == "ANALIZANDO"
    assert 0 < primera["progreso"] <= segunda["progreso"] < 1
    assert segunda["latido"] > primera["latido"]

    liberar(ruta)
    assert ejecutor.esperar_inactivo(TOPE)
    final = _fila(conectar, base_de_prueba, importacion_id)
    assert final["progreso"] == 1
    assert final["estado"] != "ANALIZANDO"


def test_tkt015_el_progreso_nunca_baja(
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
    escenario: Escenario,
) -> None:
    """TC-55 · CA-13 — un avance menor que el guardado no lo baja."""
    from cimenta.presupuesto.aplicacion.analisis_importacion import solicitar_analisis
    from cimenta.presupuesto.dominio.importacion import progreso_de_lectura

    ruta = escenario.ruta()
    importacion_id = escenario.importacion(datos_presupuesto, f"avance-desordenado:{ruta}".encode())
    ejecutor = escenario.crear()
    esperado = progreso_de_lectura(3, 5).valor

    solicitar_analisis(escenario.fabrica, ejecutor, importacion_id)
    _esperar_progreso(
        ejecutor,
        lambda: _fila(conectar, base_de_prueba, importacion_id)["progreso"],
        esperado,
    )
    # El (1, 5) llega después del (3, 5): dos latidos bastan para que ya se haya procesado.
    assert ejecutor.esperar_latidos(2, TOPE)

    fila = _fila(conectar, base_de_prueba, importacion_id)
    assert fila["estado"] == "ANALIZANDO"
    assert fila["progreso"] == esperado


def test_tkt015_resumir_avances_guarda_el_mayor() -> None:
    """TC-56 · CA-13 — por importación se conserva el avance con más hojas leídas."""
    from cimenta.presupuesto.infraestructura.ejecutor_analisis import resumir_avances

    a, b = uuid.uuid4(), uuid.uuid4()

    resumen = resumir_avances([(a, 1, 5), (a, 3, 5), (b, 2, 4), (a, 2, 5)])

    assert resumen == {a: (3, 5), b: (2, 4)}
    assert resumir_avances([]) == {}


def test_tkt015_registrar_progreso_no_sobrescribe_con_menor(
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
    fabrica_sesiones: sessionmaker[Session],
) -> None:
    """TC-55 · CA-13 — `GREATEST` en base impide bajar el progreso aunque llegue un valor menor."""
    from cimenta.presupuesto.dominio.importacion import progreso_de_lectura
    from cimenta.presupuesto.infraestructura.repositorio_importacion import registrar_progreso

    alto = progreso_de_lectura(3, 5)
    bajo = progreso_de_lectura(1, 5)
    importacion_id = datos_presupuesto.importacion(
        estado="ANALIZANDO",
        progreso=alto.valor,
    )
    with fabrica_sesiones() as sesion:
        registrar_progreso(sesion, importacion_id, bajo)
        sesion.commit()

    fila = _fila(conectar, base_de_prueba, importacion_id)
    assert fila["estado"] == "ANALIZANDO"
    assert fila["progreso"] == alto.valor


def test_tkt015_la_que_espera_turno_no_vence(
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
    escenario: Escenario,
) -> None:
    """TC-57 · CA-13, CA-16 · PA-15.4 — la encolada también late y el barrido no la toca."""
    from cimenta.presupuesto.aplicacion.analisis_importacion import solicitar_analisis
    from cimenta.presupuesto.aplicacion.barrido_importacion import definicion_barrido_importacion
    from herramientas.soporte_tkt015 import liberar
    from trabajos.barrido import barrer

    ruta = escenario.ruta()
    primera = escenario.importacion(datos_presupuesto, f"bloquear:{ruta}".encode())
    segunda = escenario.importacion(datos_presupuesto, b"anotar")
    ejecutor = escenario.crear()

    solicitar_analisis(escenario.fabrica, ejecutor, primera)
    solicitar_analisis(escenario.fabrica, ejecutor, segunda)

    assert ejecutor.esperar_latidos(2, TOPE)
    antes = _fila(conectar, base_de_prueba, segunda)["latido"]
    assert ejecutor.esperar_latidos(3, TOPE)
    despues = _fila(conectar, base_de_prueba, segunda)["latido"]
    assert despues > antes

    sesion = escenario.fabrica()
    try:
        assert barrer(sesion, definicion_barrido_importacion(timedelta(seconds=1))) == ()
        sesion.commit()
    finally:
        sesion.close()
    assert _fila(conectar, base_de_prueba, primera)["estado"] == "ANALIZANDO"
    assert _fila(conectar, base_de_prueba, segunda)["estado"] == "ANALIZANDO"

    liberar(ruta)
    assert ejecutor.esperar_inactivo(TOPE)
    assert _fila(conectar, base_de_prueba, segunda)["estado"] == "VALIDADO"


def test_hdu001_esc29_excepcion_del_trabajo(
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
    escenario: Escenario,
) -> None:
    """TC-58 · CA-14, CA-11 esc. 2 · HDU-001 esc. 29 — la excepción interrumpe y no mata el bucle."""
    from cimenta.presupuesto.aplicacion.analisis_importacion import solicitar_analisis

    fallida = escenario.importacion(datos_presupuesto, b"fallar")
    sana = escenario.importacion(datos_presupuesto, b"anotar")
    ejecutor = escenario.crear()

    with capture_logs() as registros:
        solicitar_analisis(escenario.fabrica, ejecutor, fallida)
        assert ejecutor.esperar_inactivo(TOPE)

    fila = _fila(conectar, base_de_prueba, fallida)
    assert fila["estado"] == "CON_ERRORES"
    assert fila["preparacion"] is None
    errores = _errores(conectar, base_de_prueba, fallida)
    assert [(e[0], e[1], e[2], e[3], e[4], e[5]) for e in errores] == [
        ("PROCESO_INTERRUMPIDO", _mensaje(MotivoInterrupcion.EXCEPCION), None, None, None, None)
    ]
    eventos = [r for r in registros if r["event"] == "analisis_interrumpido"]
    assert len(eventos) == 1
    assert eventos[0]["importacion_id"] == str(fallida)
    assert eventos[0]["motivo"] == "EXCEPCION"

    solicitar_analisis(escenario.fabrica, ejecutor, sana)
    assert ejecutor.esperar_inactivo(TOPE)
    assert _fila(conectar, base_de_prueba, sana)["estado"] == "VALIDADO"


def test_hdu001_esc29_trabajador_muerto(
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
    escenario: Escenario,
) -> None:
    """TC-59 · CA-14, CA-11 esc. 2 · HDU-001 esc. 29 — muere el hijo y el grupo se reemplaza."""
    from cimenta.presupuesto.aplicacion.analisis_importacion import solicitar_analisis
    from herramientas.soporte_tkt015 import liberar

    ruta = escenario.ruta()
    ejecutor = escenario.crear()
    # Un trabajo previo fija el pid del hijo original, que luego muere.
    previa = escenario.importacion(datos_presupuesto, b"anotar")
    solicitar_analisis(escenario.fabrica, ejecutor, previa)
    assert ejecutor.esperar_inactivo(TOPE)
    pid_original = _fila(conectar, base_de_prueba, previa)["preparacion"]["pid"]

    muerta = escenario.importacion(datos_presupuesto, f"morir:{ruta}".encode())
    siguiente = escenario.importacion(datos_presupuesto, b"anotar")
    solicitar_analisis(escenario.fabrica, ejecutor, muerta)
    solicitar_analisis(escenario.fabrica, ejecutor, siguiente)
    liberar(ruta)

    assert ejecutor.esperar_inactivo(TOPE)
    fila = _fila(conectar, base_de_prueba, muerta)
    assert fila["estado"] == "CON_ERRORES"
    assert fila["preparacion"] is None
    errores = _errores(conectar, base_de_prueba, muerta)
    assert [(e[0], e[1]) for e in errores] == [
        ("PROCESO_INTERRUMPIDO", _mensaje(MotivoInterrupcion.TRABAJADOR_TERMINADO))
    ]
    final = _fila(conectar, base_de_prueba, siguiente)
    assert final["estado"] == "VALIDADO"
    assert final["preparacion"]["pid"] != pid_original


def test_hdu001_esc29_archivo_ilegible(
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
    escenario: Escenario,
) -> None:
    """TC-60 · CA-14 · HDU-001 esc. 29 — si no se lee el archivo, nada llega al trabajador."""
    from cimenta.presupuesto.aplicacion.analisis_importacion import solicitar_analisis

    def no_se_puede_leer(archivo_id: uuid.UUID) -> bytes:
        raise OSError("almacén no disponible")

    importacion_id = datos_presupuesto.importacion()
    ejecutor = escenario.crear(leer_contenido=no_se_puede_leer)

    solicitar_analisis(escenario.fabrica, ejecutor, importacion_id)

    assert ejecutor.esperar_inactivo(TOPE)
    fila = _fila(conectar, base_de_prueba, importacion_id)
    assert fila["estado"] == "CON_ERRORES"
    assert fila["preparacion"] is None
    errores = _errores(conectar, base_de_prueba, importacion_id)
    assert [(e[0], e[1]) for e in errores] == [
        ("PROCESO_INTERRUMPIDO", _mensaje(MotivoInterrupcion.ARCHIVO_ILEGIBLE))
    ]
    # El grupo es de arranque perezoso: sin `submit` no se creó ningún proceso hijo.
    grupo = ejecutor._grupo  # noqa: SLF001
    assert grupo is not None
    assert not vars(grupo)["_processes"]


def test_hdu001_esc29_reintento_por_solicitar_analisis(
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
    escenario: Escenario,
    libro_catalogo: LibroCatalogo,
) -> None:
    """TC-61 · CA-18 esc. 2 · HDU-001 esc. 29 — tras una interrupción se reintenta y se valida."""
    from cimenta.presupuesto.aplicacion.analisis_importacion import solicitar_analisis
    from cimenta.presupuesto.infraestructura.ejecutor_analisis import ejecutar_en_trabajador
    from herramientas.soporte_tkt015 import libro_sintetico

    importacion_id = escenario.importacion(
        datos_presupuesto,
        libro_sintetico(libro_catalogo, conceptos=20),
        estado="CON_ERRORES",
    )
    datos_presupuesto.error_importacion(
        importacion_id=importacion_id,
        hoja=None,
        fila=None,
        columna=None,
        tipo="PROCESO_INTERRUMPIDO",
        mensaje=_mensaje(MotivoInterrupcion.REINICIO),
    )
    ejecutor = escenario.crear(trabajo=ejecutar_en_trabajador)

    solicitar_analisis(escenario.fabrica, ejecutor, importacion_id)

    assert ejecutor.esperar_inactivo(TOPE)
    fila = _fila(conectar, base_de_prueba, importacion_id)
    assert fila["estado"] == "VALIDADO"
    assert fila["progreso"] == 1
    assert fila["preparacion"]["formato"] == 1
    assert _errores(conectar, base_de_prueba, importacion_id) == []


def test_tkt015_cerrar_interrumpe_cola_y_en_curso(
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
    escenario: Escenario,
) -> None:
    """RNF-17 · cierre ordenado — cola y trabajo en curso quedan `CON_ERRORES` con `REINICIO`."""
    from cimenta.presupuesto.aplicacion.analisis_importacion import solicitar_analisis
    from herramientas.soporte_tkt015 import liberar

    ruta = escenario.ruta()
    en_curso = escenario.importacion(datos_presupuesto, f"bloquear:{ruta}".encode())
    encolada = escenario.importacion(datos_presupuesto, b"anotar")
    ejecutor = escenario.crear()

    solicitar_analisis(escenario.fabrica, ejecutor, en_curso)
    solicitar_analisis(escenario.fabrica, ejecutor, encolada)
    assert ejecutor.esperar_latidos(1, TOPE)

    ejecutor.cerrar()
    liberar(ruta)

    for importacion_id in (en_curso, encolada):
        fila = _fila(conectar, base_de_prueba, importacion_id)
        assert fila["estado"] == "CON_ERRORES"
        assert fila["preparacion"] is None
        errores = _errores(conectar, base_de_prueba, importacion_id)
        assert [(e[0], e[1]) for e in errores] == [
            ("PROCESO_INTERRUMPIDO", _mensaje(MotivoInterrupcion.REINICIO))
        ]


def test_hdu001_esc29_ejecutor_cerrado_deja_reinicio(
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
    escenario: Escenario,
) -> None:
    """TC-62 · CA-12, CA-14 · HDU-001 esc. 29 — con el ejecutor cerrado queda REINICIO."""
    from cimenta.presupuesto.aplicacion.analisis_importacion import solicitar_analisis
    from cimenta.presupuesto.infraestructura.ejecutor_analisis import EjecutorCerrado

    importacion_id = escenario.importacion(datos_presupuesto, b"anotar")
    ejecutor = escenario.crear()
    ejecutor.cerrar()

    with pytest.raises(EjecutorCerrado):
        solicitar_analisis(escenario.fabrica, ejecutor, importacion_id)

    fila = _fila(conectar, base_de_prueba, importacion_id)
    assert fila["estado"] == "CON_ERRORES"
    assert fila["preparacion"] is None
    errores = _errores(conectar, base_de_prueba, importacion_id)
    assert [(e[0], e[1]) for e in errores] == [
        ("PROCESO_INTERRUMPIDO", _mensaje(MotivoInterrupcion.REINICIO))
    ]
