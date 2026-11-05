"""Ejecutor del análisis de importación en un proceso aparte (TKT-015b).

Un grupo de un solo proceso (`spawn`) lee y analiza el libro; un hilo despachador, único dueño
del estado, saca los trabajos de la cola, vacía el avance que el hijo reporta por una cola
compartida, renueva el latido y cierra cada importación por el caso de uso. El hijo nunca toca
la base de datos. Construir el ejecutor no crea procesos ni hilos: nacen en el primer `encolar`.
"""

from __future__ import annotations

import multiprocessing
import queue
import threading
from collections import deque
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import Future, ProcessPoolExecutor, wait
from concurrent.futures.process import BrokenProcessPool
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Protocol
from uuid import UUID

import structlog

from cimenta.presupuesto.dominio.importacion import MotivoInterrupcion, TrabajoAnalisis
from cimenta.presupuesto.infraestructura.trabajo_analisis import (
    ResultadoAnalisis,
    analizar_contenido,
)

_registro = structlog.get_logger("cimenta.presupuesto")

type FuncionTrabajo = Callable[[UUID, bytes, Mapping[str, str]], ResultadoAnalisis]


class Seguimiento(Protocol):
    """Lo que el ejecutor necesita de la persistencia; cada método es una transacción corta."""

    def latir(self, ids: Sequence[UUID]) -> None: ...

    def avanzar(self, importacion_id: UUID, hojas_leidas: int, hojas_totales: int) -> None: ...

    def terminar(self, importacion_id: UUID, resultado: ResultadoAnalisis) -> None: ...

    def interrumpir(self, importacion_id: UUID, motivo: MotivoInterrupcion) -> None: ...


class EjecutorCerrado(RuntimeError):
    """El ejecutor ya se cerró y no admite más trabajos."""


# Cola de avance del proceso hijo: la fija `_iniciar_trabajador` al nacer el hijo.
_cola_del_trabajador: Any = None


def _iniciar_trabajador(cola: Any) -> None:
    global _cola_del_trabajador
    _cola_del_trabajador = cola


def notificar_avance(importacion_id: UUID, hojas_leidas: int, hojas_totales: int) -> None:
    """Se ejecuta en el hijo: deja el avance en la cola compartida; sin cola, no hace nada."""
    cola = _cola_del_trabajador
    if cola is None:
        return
    cola.put_nowait((importacion_id, hojas_leidas, hojas_totales))


def ejecutar_en_trabajador(
    importacion_id: UUID,
    contenido: bytes,
    insumos: Mapping[str, str],
) -> ResultadoAnalisis:
    """Función del hijo: analiza el contenido y reporta el avance de lectura."""
    return analizar_contenido(
        contenido,
        insumos,
        al_avanzar=lambda leidas, totales: notificar_avance(importacion_id, leidas, totales),
    )


def resumir_avances(mensajes: Sequence[tuple[UUID, int, int]]) -> dict[UUID, tuple[int, int]]:
    """Por importación, el avance con más hojas leídas."""
    resumen: dict[UUID, tuple[int, int]] = {}
    for importacion_id, leidas, totales in mensajes:
        actual = resumen.get(importacion_id)
        if actual is None or leidas > actual[0]:
            resumen[importacion_id] = (leidas, totales)
    return resumen


@dataclass(slots=True)
class _EnCurso:
    trabajo: TrabajoAnalisis
    futuro: Future[ResultadoAnalisis] | None = None


class EjecutorAnalisis:
    """Un trabajo a la vez en un proceso aparte, con latido y avance hacia la base."""

    def __init__(
        self,
        *,
        seguimiento: Seguimiento,
        leer_contenido: Callable[[UUID], bytes],
        intervalo_latido: timedelta,
        trabajo: FuncionTrabajo = ejecutar_en_trabajador,
    ) -> None:
        self._seguimiento = seguimiento
        self._leer_contenido = leer_contenido
        self._intervalo = intervalo_latido.total_seconds()
        self._trabajo = trabajo
        self._condicion = threading.Condition()
        self._cola: deque[TrabajoAnalisis] = deque()
        self._en_curso: _EnCurso | None = None
        self._cerrado = False
        self._latidos = 0
        self._hilo: threading.Thread | None = None
        self._grupo: ProcessPoolExecutor | None = None
        self._cola_de_avance: Any = None

    # ------------------------------------------------------------------ interfaz pública

    def encolar(self, trabajo: TrabajoAnalisis) -> None:
        with self._condicion:
            if self._cerrado:
                raise EjecutorCerrado("el ejecutor de análisis está cerrado")
            if self._hilo is None:
                self._crear_grupo()
                self._hilo = threading.Thread(
                    target=self._bucle,
                    name="cimenta-despachador-analisis",
                    daemon=True,
                )
                self._hilo.start()
            self._cola.append(trabajo)
            self._condicion.notify_all()

    def cerrar(self, *, espera_maxima: float = 10.0) -> None:
        """Detiene el despachador, interrumpe cola y trabajo en curso con `REINICIO` y cierra el grupo."""
        pendientes: list[UUID] = []
        with self._condicion:
            if self._en_curso is not None:
                pendientes.append(self._en_curso.trabajo.importacion_id)
            pendientes.extend(t.importacion_id for t in self._cola)
            self._cola.clear()
            self._cerrado = True
            self._condicion.notify_all()
            hilo = self._hilo
        for importacion_id in pendientes:
            self._interrumpir(importacion_id, MotivoInterrupcion.REINICIO)
        if hilo is not None:
            hilo.join(timeout=espera_maxima)
        grupo = self._grupo
        if grupo is not None:
            grupo.shutdown(wait=False, cancel_futures=True)

    def esperar_latidos(self, minimo: int, espera_maxima: float) -> bool:
        """Espera `minimo` latidos con identificadores, contados desde esta llamada."""
        with self._condicion:
            base = self._latidos
            return self._condicion.wait_for(
                lambda: self._latidos - base >= minimo,
                timeout=espera_maxima,
            )

    def esperar_inactivo(self, espera_maxima: float) -> bool:
        """Espera a que la cola esté vacía y nada en curso."""
        with self._condicion:
            return self._condicion.wait_for(
                lambda: not self._cola and self._en_curso is None,
                timeout=espera_maxima,
            )

    # ------------------------------------------------------------------ grupo de procesos

    def _crear_grupo(self) -> None:
        contexto = multiprocessing.get_context("spawn")
        self._cola_de_avance = contexto.Queue()
        self._grupo = ProcessPoolExecutor(
            max_workers=1,
            mp_context=contexto,
            initializer=_iniciar_trabajador,
            initargs=(self._cola_de_avance,),
        )

    def _reemplazar_grupo(self) -> None:
        anterior = self._grupo
        cola_anterior = self._cola_de_avance
        if anterior is not None:
            anterior.shutdown(wait=False, cancel_futures=True)
        if cola_anterior is not None:
            cola_anterior.close()
            cola_anterior.cancel_join_thread()
        self._crear_grupo()

    # ------------------------------------------------------------------ hilo despachador

    def _bucle(self) -> None:
        while True:
            with self._condicion:
                if self._cerrado:
                    return
            try:
                self._vuelta()
            except Exception:
                _registro.exception("despachador_error")
                with self._condicion:
                    if not self._cerrado:
                        self._condicion.wait(timeout=self._intervalo)

    def _vuelta(self) -> None:
        self._tomar_siguiente()
        self._esperar()
        self._vaciar_avance()
        self._latir()
        self._cerrar_si_termino()

    def _tomar_siguiente(self) -> None:
        with self._condicion:
            if self._en_curso is not None or not self._cola:
                return
            en_curso = _EnCurso(trabajo=self._cola.popleft())
            self._en_curso = en_curso
        trabajo = en_curso.trabajo
        try:
            contenido = self._leer_contenido(trabajo.archivo_id)
        except Exception:
            self._interrumpir(trabajo.importacion_id, MotivoInterrupcion.ARCHIVO_ILEGIBLE)
            self._liberar_en_curso()
            return
        grupo = self._grupo
        if grupo is None:
            self._interrumpir(trabajo.importacion_id, MotivoInterrupcion.TRABAJADOR_TERMINADO)
            self._liberar_en_curso()
            return
        try:
            en_curso.futuro = grupo.submit(
                self._trabajo,
                trabajo.importacion_id,
                contenido,
                dict(trabajo.insumos_existentes),
            )
        except (BrokenProcessPool, RuntimeError):
            self._interrumpir(trabajo.importacion_id, MotivoInterrupcion.TRABAJADOR_TERMINADO)
            self._reemplazar_grupo()
            self._liberar_en_curso()

    def _esperar(self) -> None:
        en_curso = self._en_curso
        if en_curso is not None and en_curso.futuro is not None:
            wait([en_curso.futuro], timeout=self._intervalo)
            return
        with self._condicion:
            if not self._cola and not self._cerrado:
                self._condicion.wait(timeout=self._intervalo)

    def _vaciar_avance(self) -> None:
        cola = self._cola_de_avance
        mensajes: list[tuple[UUID, int, int]] = []
        while True:
            try:
                mensajes.append(cola.get_nowait())
            except queue.Empty:
                break
            except Exception:
                _registro.exception("avance_colado_invalido")
                break
        for importacion_id, (leidas, totales) in resumir_avances(mensajes).items():
            try:
                self._seguimiento.avanzar(importacion_id, leidas, totales)
            except Exception:
                _registro.exception("avance_no_registrado", importacion_id=str(importacion_id))

    def _latir(self) -> None:
        with self._condicion:
            ids = [t.importacion_id for t in self._cola]
            if self._en_curso is not None:
                ids.insert(0, self._en_curso.trabajo.importacion_id)
        if not ids:
            return
        try:
            self._seguimiento.latir(ids)
        except Exception:
            _registro.exception("latido_no_registrado")
        with self._condicion:
            self._latidos += 1
            self._condicion.notify_all()

    def _cerrar_si_termino(self) -> None:
        en_curso = self._en_curso
        if en_curso is None or en_curso.futuro is None or not en_curso.futuro.done():
            return
        importacion_id = en_curso.trabajo.importacion_id
        try:
            resultado = en_curso.futuro.result()
        except BrokenProcessPool:
            self._interrumpir(importacion_id, MotivoInterrupcion.TRABAJADOR_TERMINADO)
            self._reemplazar_grupo()
        except Exception:
            self._interrumpir(importacion_id, MotivoInterrupcion.EXCEPCION)
        else:
            try:
                self._seguimiento.terminar(importacion_id, resultado)
            except Exception:
                _registro.exception("resultado_no_registrado", importacion_id=str(importacion_id))
        self._liberar_en_curso()

    def _interrumpir(self, importacion_id: UUID, motivo: MotivoInterrupcion) -> None:
        _registro.warning(
            "analisis_interrumpido",
            importacion_id=str(importacion_id),
            motivo=motivo.value,
        )
        try:
            self._seguimiento.interrumpir(importacion_id, motivo)
        except Exception:
            _registro.exception("interrupcion_no_registrada", importacion_id=str(importacion_id))

    def _liberar_en_curso(self) -> None:
        with self._condicion:
            self._en_curso = None
            self._condicion.notify_all()
