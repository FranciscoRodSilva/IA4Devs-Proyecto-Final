"""Aplica mutantes M-13…M-23 de TKT-015b, ejecuta pytest y revierte. Solo para cierre B7."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

RAIZ_BACKEND = Path(__file__).resolve().parents[1]

ARCHIVOS: dict[str, str] = {}


def _leer(ruta: Path) -> str:
    return ruta.read_text(encoding="utf-8")


def _guardar(ruta: Path) -> None:
    clave = str(ruta)
    if clave not in ARCHIVOS:
        ARCHIVOS[clave] = _leer(ruta)


def _restaurar_todo() -> None:
    for clave, texto in ARCHIVOS.items():
        Path(clave).write_text(texto, encoding="utf-8")


def _escribir(ruta: Path, texto: str) -> None:
    _guardar(ruta)
    ruta.write_text(texto, encoding="utf-8")


def _pytest(tests: list[str]) -> int:
    cmd = ["uv", "run", "pytest", *tests, "-q", "--tb=no"]
    proc = subprocess.run(cmd, cwd=RAIZ_BACKEND, capture_output=True, text=True)
    sys.stdout.write(proc.stdout)
    sys.stderr.write(proc.stderr)
    return proc.returncode


def _fallo_esperado(codigo: int) -> bool:
    return codigo != 0


Mutante = tuple[str, Callable[[], None], list[str]]


def _m13() -> None:
    ruta = RAIZ_BACKEND / "trabajos/barrido.py"
    t = _leer(ruta)
    t = t.replace(
        "            or_(\n                t.c[definicion.columna_marca].is_(None),\n                t.c[definicion.columna_marca] < limite,\n            ),",
        "            t.c[definicion.columna_marca] < limite,",
        1,
    )
    _escribir(ruta, t)


def _m14() -> None:
    ruta = RAIZ_BACKEND / "trabajos/barrido.py"
    t = _leer(ruta)
    t = t.replace(
        "            t.c[definicion.columna_estado] == definicion.estado_intermedio,\n            or_(",
        "            or_(",
        1,
    )
    _escribir(ruta, t)


def _m15() -> None:
    ruta = RAIZ_BACKEND / "trabajos/barrido.py"
    t = _leer(ruta)
    t = t.replace(
        "t.c[definicion.columna_marca] < limite,",
        "t.c[definicion.columna_marca] > limite,",
        1,
    )
    _escribir(ruta, t)


def _m16() -> None:
    ruta = RAIZ_BACKEND / "cimenta/presupuesto/infraestructura/ejecutor_analisis.py"
    t = _leer(ruta)
    t = t.replace(
        "            ids = [t.importacion_id for t in self._cola]\n            if self._en_curso is not None:\n                ids.insert(0, self._en_curso.trabajo.importacion_id)",
        "            ids = []\n            if self._en_curso is not None:\n                ids = [self._en_curso.trabajo.importacion_id]",
        1,
    )
    _escribir(ruta, t)


def _m17() -> None:
    ruta = RAIZ_BACKEND / "cimenta/presupuesto/infraestructura/ejecutor_analisis.py"
    t = _leer(ruta)
    t = t.replace("max_workers=1,", "max_workers=2,", 1)
    viejo = """        en_curso.futuro = grupo.submit(
            self._trabajo,
            trabajo.importacion_id,
            contenido,
            dict(trabajo.insumos_existentes),
        )"""
    nuevo = """        en_curso.futuro = grupo.submit(
            self._trabajo,
            trabajo.importacion_id,
            contenido,
            dict(trabajo.insumos_existentes),
        )
        while self._cola:
            extra = self._cola.popleft()
            try:
                extra_contenido = self._leer_contenido(extra.archivo_id)
            except Exception:
                continue
            grupo.submit(
                self._trabajo,
                extra.importacion_id,
                extra_contenido,
                dict(extra.insumos_existentes),
            )"""
    t = t.replace(viejo, nuevo, 1)
    _escribir(ruta, t)


def _m18() -> None:
    ruta = RAIZ_BACKEND / "cimenta/presupuesto/infraestructura/repositorio_importacion.py"
    t = _leer(ruta)
    t = t.replace(
        "progreso=func.greatest(func.coalesce(importacion.c.progreso, 0), progreso.valor),",
        "progreso=progreso.valor,",
        1,
    )
    _escribir(ruta, t)


def _m19() -> None:
    ruta = RAIZ_BACKEND / "cimenta/presupuesto/infraestructura/ejecutor_analisis.py"
    t = _leer(ruta)
    t = t.replace(
        """    for importacion_id, leidas, totales in mensajes:
        actual = resumen.get(importacion_id)
        if actual is None or leidas > actual[0]:
            resumen[importacion_id] = (leidas, totales)""",
        """    for importacion_id, leidas, totales in mensajes:
        resumen[importacion_id] = (leidas, totales)""",
        1,
    )
    _escribir(ruta, t)


def _m20() -> None:
    ruta = RAIZ_BACKEND / "cimenta/presupuesto/dominio/importacion.py"
    t = _leer(ruta)
    t = t.replace("ROUND_DOWN", "ROUND_HALF_UP", 1)
    t = t.replace(
        "from decimal import ROUND_DOWN, Decimal", "from decimal import ROUND_HALF_UP, Decimal", 1
    )
    _escribir(ruta, t)


def _m21() -> None:
    ruta = RAIZ_BACKEND / "cimenta/presupuesto/infraestructura/lector_catalogo.py"
    t = _leer(ruta)
    t = t.replace(
        "            if nombre == catalogo.hoja:\n                continue",
        "            if nombre == catalogo.hoja:\n                contador += 1\n                if al_avanzar is not None:\n                    al_avanzar(contador, total)\n                continue",
        1,
    )
    _escribir(ruta, t)


def _m22() -> None:
    ruta = RAIZ_BACKEND / "servidor/fabrica.py"
    t = _leer(ruta)
    t = t.replace(
        "        if motor is None and not variables_de_base_presentes(entorno_efectivo):",
        "        if False and motor is None and not variables_de_base_presentes(entorno_efectivo):",
        1,
    )
    _escribir(ruta, t)


def _m23() -> None:
    ruta = RAIZ_BACKEND / "servidor/fabrica.py"
    t = _leer(ruta)
    t = t.replace(
        "        cuentas = await run_in_threadpool(\n            barrer_todas,\n            fabrica_sesiones,\n            [\n                definicion_barrido_importacion(\n                    timedelta(seconds=ajustes.trabajos_umbral_vencimiento)\n                )\n            ],\n        )",
        "        try:\n            cuentas = await run_in_threadpool(\n                barrer_todas,\n                fabrica_sesiones,\n                [\n                    definicion_barrido_importacion(\n                        timedelta(seconds=ajustes.trabajos_umbral_vencimiento)\n                    )\n                ],\n            )\n        except Exception:\n            cuentas = {}",
        1,
    )
    _escribir(ruta, t)


MUTANTES: list[Mutante] = [
    (
        "M-13",
        _m13,
        [
            "tests/test_tkt015_barrido_importacion.py::test_hdu001_esc29_barrido_latido_nulo_es_vencido"
        ],
    ),
    (
        "M-14",
        _m14,
        ["tests/test_tkt015_barrido_importacion.py::test_hdu001_esc29_barrido_no_toca_lo_vivo"],
    ),
    (
        "M-15",
        _m15,
        [
            "tests/test_tkt015_barrido_importacion.py::test_hdu001_esc29_barrido_marca_la_interrumpida",
            "tests/test_tkt015_barrido_importacion.py::test_hdu001_esc29_barrido_no_toca_lo_vivo",
        ],
    ),
    (
        "M-16",
        _m16,
        ["tests/test_tkt015_ejecutor.py::test_tkt015_la_que_espera_turno_no_vence"],
    ),
    (
        "M-17",
        _m17,
        ["tests/test_tkt015_ejecutor.py::test_hdu001_esc29_trabajador_muerto"],
    ),
    (
        "M-18",
        _m18,
        ["tests/test_tkt015_ejecutor.py::test_tkt015_registrar_progreso_no_sobrescribe_con_menor"],
    ),
    (
        "M-19",
        _m19,
        ["tests/test_tkt015_ejecutor.py::test_tkt015_resumir_avances_guarda_el_mayor"],
    ),
    (
        "M-20",
        _m20,
        ["tests/test_tkt015_avance.py::test_hdu001_esc04_progreso_de_lectura[4-7-esperado3]"],
    ),
    (
        "M-21",
        _m21,
        [
            "tests/test_tkt015_avance.py::test_tkt015_lector_con_avance_no_cambia_el_resultado_cuatro_hojas[0]"
        ],
    ),
    (
        "M-22",
        _m22,
        [
            "tests/test_tkt015_arranque.py::test_tkt015_sin_variables_de_base_el_servidor_arranca",
            "tests/test_servidor_arranque.py::test_tkt006_car4_fastapi_dev_sin_variables_de_base_publica_identidad",
        ],
    ),
    (
        "M-23",
        _m23,
        ["tests/test_tkt015_arranque.py::test_tkt015_con_base_y_barrido_fallido_no_arranca"],
    ),
]


def main() -> int:
    resultados: list[tuple[str, bool, str]] = []
    try:
        for nombre, aplicar, tests in MUTANTES:
            _restaurar_todo()
            ARCHIVOS.clear()
            aplicar()
            codigo = _pytest(tests)
            ok = _fallo_esperado(codigo)
            resultados.append((nombre, ok, f"exit={codigo}"))
            print(f"{nombre}: {'ROJO OK' if ok else 'FALLO (sigue verde)'} {tests}")
    finally:
        _restaurar_todo()
        ARCHIVOS.clear()

    fallidos = [n for n, ok, _ in resultados if not ok]
    if fallidos:
        print("Mutantes que no cayeron:", ", ".join(fallidos))
        return 1
    print("11/11 mutantes cayeron en rojo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
