"""Aplica mutantes M-01…M-12 de TKT-015a, ejecuta pytest y revierte. Solo para cierre A9."""

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


def _m01() -> None:
    ruta = RAIZ_BACKEND / "cimenta/presupuesto/dominio/clasificacion_importacion.py"
    t = _leer(ruta)
    t = t.replace(
        "CausaHallazgo.ERROR_DE_FORMULA: TipoErrorImportacion.REF_ROTA,",
        "CausaHallazgo.ERROR_DE_FORMULA: TipoErrorImportacion.SIN_CONCEPTOS,",
        1,
    )
    _escribir(ruta, t)


def _m02() -> None:
    ruta = RAIZ_BACKEND / "cimenta/presupuesto/dominio/clasificacion_importacion.py"
    t = _leer(ruta)
    t = t.replace(
        "        CausaHallazgo.TIPO_EN_CONFLICTO: TipoErrorImportacion.DUPLICADO,\n",
        "",
        1,
    )
    _escribir(ruta, t)


def _m03() -> None:
    ruta = RAIZ_BACKEND / "cimenta/presupuesto/dominio/clasificacion_importacion.py"
    t = _leer(ruta)
    t = t.replace(
        "    if hallazgo.columna != _COLUMNA_RENDIMIENTO:\n        return False\n",
        "",
        1,
    )
    _escribir(ruta, t)


def _m04() -> None:
    ruta = RAIZ_BACKEND / "cimenta/presupuesto/dominio/clasificacion_importacion.py"
    t = _leer(ruta)
    t = t.replace(
        "        claves_desc = {normalizar_clave_insumo(c.descripcion) for c in conceptos}",
        "        claves_desc = {c.descripcion for c in conceptos if c.descripcion is not None}",
        1,
    )
    _escribir(ruta, t)


def _m05() -> None:
    ruta = RAIZ_BACKEND / "cimenta/presupuesto/dominio/clasificacion_importacion.py"
    t = _leer(ruta)
    t = t.replace(
        "        if len(claves_desc) <= 1:\n            continue",
        "        if len(conceptos) <= 1:\n            continue",
        1,
    )
    _escribir(ruta, t)


def _m06() -> None:
    ruta = RAIZ_BACKEND / "cimenta/presupuesto/dominio/importacion.py"
    t = _leer(ruta)
    t = t.replace(
        "    if len(errores) == 0:\n        return EstadoImportacion.VALIDADO\n    return EstadoImportacion.CON_ERRORES",
        "    if len(errores) == 0:\n        return EstadoImportacion.VALIDADO\n    if len(errores) > 1:\n        return EstadoImportacion.CON_ERRORES\n    return EstadoImportacion.VALIDADO",
        1,
    )
    _escribir(ruta, t)


def _m07() -> None:
    ruta = RAIZ_BACKEND / "cimenta/presupuesto/dominio/importacion.py"
    t = _leer(ruta)
    t = t.replace(
        "    if estado is EstadoImportacion.CON_ERRORES:\n        return tipos_de_error == frozenset({TipoErrorImportacion.PROCESO_INTERRUMPIDO})",
        "    if estado is EstadoImportacion.CON_ERRORES:\n        return True",
        1,
    )
    _escribir(ruta, t)


def _m08() -> None:
    ruta = RAIZ_BACKEND / "cimenta/presupuesto/infraestructura/repositorio_importacion.py"
    t = _leer(ruta)
    t = t.replace("\n        .with_for_update()", "", 1)
    _escribir(ruta, t)


def _m09() -> None:
    ruta = RAIZ_BACKEND / "cimenta/presupuesto/infraestructura/repositorio_importacion.py"
    t = _leer(ruta)
    t = t.replace(
        "            importacion.c.id == importacion_id,\n            importacion.c.estado == EstadoImportacion.ANALIZANDO.value,\n        )",
        "            importacion.c.id == importacion_id,\n        )",
        1,
    )
    _escribir(ruta, t)


def _m10() -> None:
    ruta = RAIZ_BACKEND / "cimenta/presupuesto/dominio/clasificacion_importacion.py"
    t = _leer(ruta)
    t = t.replace(
        "CausaHallazgo.CONCEPTO_SIN_PARTIDA: TipoErrorImportacion.REF_ROTA,",
        "CausaHallazgo.CONCEPTO_SIN_PARTIDA: TipoErrorImportacion.SIN_CONCEPTOS,",
        1,
    )
    _escribir(ruta, t)


def _m11() -> None:
    ruta = RAIZ_BACKEND / "cimenta/presupuesto/dominio/clasificacion_importacion.py"
    t = _leer(ruta)
    viejo = """        elif error.hoja is not None and error.hoja != hoja_cat:
            hojas.add(error.hoja)"""
    nuevo = """        elif error.tipo is TipoErrorImportacion.DUPLICADO and error.valor_original:
            filas_del_codigo(error.valor_original)
        elif error.hoja is not None and error.hoja != hoja_cat:
            hojas.add(error.hoja)"""
    t = t.replace(viejo, nuevo, 1)
    _escribir(ruta, t)


def _m12() -> None:
    ruta = RAIZ_BACKEND / "cimenta/presupuesto/infraestructura/repositorio_importacion.py"
    t = _leer(ruta)
    t = t.replace(
        "        .values(\n            estado=EstadoImportacion.CON_ERRORES.value,\n            latido=func.now(),\n        )",
        '        .values(\n            estado=EstadoImportacion.CON_ERRORES.value,\n            latido=func.now(),\n            preparacion={"formato": 1},\n        )',
        1,
    )
    _escribir(ruta, t)


MUTANTES: list[Mutante] = [
    (
        "M-01",
        _m01,
        [
            "tests/test_tkt015_clasificacion.py::test_hdu001_esc06_ref_rota_conserva_la_celda",
            "tests/test_tkt015_analisis.py::test_hdu001_esc06_ref_rota_seis_errores_y_197_en_preparacion",
        ],
    ),
    (
        "M-02",
        _m02,
        ["tests/test_tkt015_clasificacion.py::test_hdu001_esc06_toda_causa_tiene_tipo_y_mensaje"],
    ),
    (
        "M-03",
        _m03,
        [
            "tests/test_tkt015_clasificacion.py::test_hdu001_esc28_rendimiento_ausente_solo_en_la_celda_de_rendimiento"
        ],
    ),
    (
        "M-04",
        _m04,
        [
            "tests/test_tkt015_clasificacion_libro.py::test_hdu001_esc09_misma_descripcion_normalizada_no_es_duplicado"
        ],
    ),
    (
        "M-05",
        _m05,
        [
            "tests/test_tkt015_clasificacion_libro.py::test_hdu001_esc09_misma_descripcion_normalizada_no_es_duplicado",
            "tests/test_tkt015_archivos_reales.py::test_hdu001_esc09_eniti_sin_duplicados",
        ],
    ),
    (
        "M-06",
        _m06,
        [
            "tests/test_tkt015_importacion.py::test_hdu001_esc04_estado_tras_analisis",
            "tests/test_tkt015_analisis.py::test_hdu001_esc07_sin_apu_persistido",
        ],
    ),
    (
        "M-07",
        _m07,
        [
            "tests/test_tkt015_importacion.py::test_tkt015_estados_que_admiten_analisis",
            "tests/test_tkt015_analisis.py::test_tkt015_estado_que_no_admite_analisis",
        ],
    ),
    (
        "M-08",
        _m08,
        ["tests/test_tkt015_analisis.py::test_tkt015_dos_solicitudes_simultaneas"],
    ),
    (
        "M-09",
        _m09,
        ["tests/test_tkt015_analisis.py::test_tkt015_resultado_tardio_no_pisa_el_estado"],
    ),
    (
        "M-10",
        _m10,
        [
            "tests/test_tkt015_clasificacion.py::test_hdu001_esc06_toda_causa_tiene_tipo_y_mensaje",
            "tests/test_tkt015_archivos_reales.py::test_hdu001_esc06_union_square_fila_a_fila",
        ],
    ),
    (
        "M-11",
        _m11,
        [
            "tests/test_tkt015_clasificacion_libro.py::test_tkt015_filas_y_hojas_rechazadas",
            "tests/test_tkt015_archivos_reales.py::test_tkt015_eniti_48_errores",
        ],
    ),
    (
        "M-12",
        _m12,
        ["tests/test_tkt015_analisis.py::test_hdu001_esc29_interrupcion_no_deja_preparacion"],
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
    print("12/12 mutantes cayeron en rojo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
