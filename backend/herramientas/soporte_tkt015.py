"""Utilidades compartidas de las pruebas TKT-015 (clasificación e importación)."""

from __future__ import annotations

import os
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from cimenta.presupuesto.dominio.catalogo import (
    CatalogoLeido,
    CausaHallazgo,
    ConceptoLeido,
    Hallazgo,
    Ruta,
)
from cimenta.presupuesto.infraestructura.ejecutor_analisis import notificar_avance
from cimenta.presupuesto.infraestructura.trabajo_analisis import ResultadoAnalisis
from herramientas.soporte_tkt013 import LibroCatalogoPrueba
from herramientas.soporte_tkt014 import catalogo_con_codigos, escribir_hoja_apu_sintetica

CampoConcepto = Literal["codigo", "descripcion", "unidad", "cantidad", "precio_unitario", "importe"]

HOJA_CATALOGO_SINTETICO = "CATALOGO"

_INDICE_CAMPO: dict[CampoConcepto, int] = {
    "codigo": 0,
    "descripcion": 1,
    "unidad": 2,
    "cantidad": 3,
    "precio_unitario": 4,
    "importe": 5,
}


def hallazgo(
    causa: CausaHallazgo,
    *,
    hoja: str | None = "CATALOGO",
    fila: int | None = 57,
    columna: str | None = "F",
    valor: str | None = "#REF!",
    detalle: str | None = None,
) -> Hallazgo:
    return Hallazgo(
        causa=causa,
        hoja=hoja,
        fila=fila,
        columna=columna,
        valor_original=valor,
        detalle=detalle,
    )


def hallazgo_ejemplo(causa: CausaHallazgo) -> Hallazgo:
    """Hallazgo mínimo por causa para comprobar tipo y mensaje (TC-05, TC-39)."""
    if causa in {
        CausaHallazgo.HOJA_NO_LOCALIZADA,
        CausaHallazgo.HOJA_AMBIGUA,
    }:
        return hallazgo(causa, hoja=None, fila=None, columna=None, valor="x", detalle="det")
    if causa is CausaHallazgo.ENCABEZADO_NO_LOCALIZADO:
        return hallazgo(causa, hoja="CAT", fila=8, columna="A")
    if causa is CausaHallazgo.COLUMNA_NO_LOCALIZADA:
        return hallazgo(causa, hoja="CAT", fila=8, columna="A", valor="Unidad", detalle="no existe")
    if causa is CausaHallazgo.NINGUN_CONCEPTO:
        return hallazgo(causa, hoja="CAT", fila=8, columna="A")
    if causa is CausaHallazgo.CONCEPTO_SIN_PARTIDA:
        return hallazgo(causa, fila=12, columna="A")
    if causa is CausaHallazgo.PROFUNDIDAD_EXCEDIDA:
        return hallazgo(causa, valor="NIVEL EXTRA")
    if causa in (CausaHallazgo.PU_NO_CUADRA, CausaHallazgo.PU_NO_VERIFICABLE):
        return hallazgo(causa, detalle="detalle de cuadre")
    if causa is CausaHallazgo.ANALISIS_SIN_CODIGO:
        return hallazgo(causa, hoja="APU 01", fila=12, columna="C")
    if causa is CausaHallazgo.CODIGO_EN_VARIAS_HOJAS:
        return hallazgo(causa, hoja="APU 01", valor="620001", detalle="APU 02")
    if causa is CausaHallazgo.CODIGO_SIN_CONCEPTO:
        return hallazgo(causa, hoja="APU 01", valor="X-999", fila=12, columna="C")
    if causa in (CausaHallazgo.UNIDAD_EN_CONFLICTO, CausaHallazgo.TIPO_EN_CONFLICTO):
        return hallazgo(causa, detalle="M2 vs KG")
    return hallazgo(causa)


def catalogo_con_descripciones(
    filas: Sequence[tuple[int, str, str | None]],
) -> CatalogoLeido:
    """Catálogo con código y descripción por fila (pruebas de duplicados TKT-015)."""
    return catalogo_en_memoria(filas)


def catalogo_en_memoria(
    filas: Sequence[tuple[int, str, str | None]],
) -> CatalogoLeido:
    """Catálogo mínimo con código y descripción por fila (pruebas TKT-015)."""
    if not filas:
        return catalogo_con_codigos(())
    ruta = Ruta(raiz=None, nivel=None, area=None, partida=None)
    conceptos = tuple(
        ConceptoLeido(
            fila=fila,
            codigo=codigo,
            descripcion=descripcion,
            unidad="M2",
            cantidad=None,
            precio_unitario=None,
            importe=None,
            ruta=ruta,
        )
        for fila, codigo, descripcion in filas
    )
    return CatalogoLeido(
        hoja="CATALOGO",
        fila_encabezado=8,
        nodos=(),
        conceptos=conceptos,
        hallazgos=(),
    )


def libro_sintetico(
    libro: LibroCatalogoPrueba,
    *,
    conceptos: int = 200,
    codigos: Sequence[str] = ("P-001", "P-002"),
    codigo_en: Mapping[int, str] | None = None,
    descripciones: Mapping[int, str] | None = None,
    unidad_en: Mapping[int, str] | None = None,
    rotos: Mapping[tuple[int, CampoConcepto], str] | None = None,
    hojas_apu: Sequence[str] | None = None,
    variantes_apu: Mapping[str, Mapping[str, Any]] | None = None,
    catalogo_vacio: bool = False,
    posicion_catalogo: int = 0,
) -> bytes:
    """Libro .xlsx sintético con catálogo en `CATALOGO` y hojas `APU {codigo}` (TKT-015a)."""
    filas_concepto = range(9, 9 + conceptos)
    codigos_distintos: list[str] = []
    vistos: set[str] = set()
    for fila in filas_concepto:
        codigo = (codigo_en or {}).get(fila, codigos[(fila - 9) % len(codigos)])
        if codigo not in vistos:
            vistos.add(codigo)
            codigos_distintos.append(codigo)

    codigos_apu = list(hojas_apu) if hojas_apu is not None else codigos_distintos
    nombres_hojas = [f"APU {codigo}" for codigo in codigos_apu]
    nombres_hojas.insert(posicion_catalogo, HOJA_CATALOGO_SINTETICO)

    variantes = variantes_apu or {}

    for nombre in nombres_hojas:
        if nombre == HOJA_CATALOGO_SINTETICO:
            libro.nueva_hoja(nombre)
            if catalogo_vacio:
                continue
            for fila in range(1, 4):
                libro.escribir_fila(nombre, fila, (None,))
            libro.escribir_fila(
                nombre,
                4,
                ("Código", "DESCRIPCION", "Unidad", "Cantidad", "P.U.", "IMPORTE"),
            )
            for fila, valores in (
                (5, (None, "RAIZ SINTETICA")),
                (6, (None, "NIVEL 1")),
                (7, (None, "ZONA A")),
                (8, (None, "PARTIDA MUROS")),
            ):
                libro.escribir_fila(nombre, fila, valores)
            for fila in filas_concepto:
                codigo = (codigo_en or {}).get(fila, codigos[(fila - 9) % len(codigos)])
                descripcion = (descripciones or {}).get(fila, f"CONCEPTO {codigo}")
                unidad = (unidad_en or {}).get(fila, "M2")
                celdas: list[Any] = [codigo, descripcion, unidad, 1, 10, 10]
                if rotos:
                    for (fila_r, campo), valor in rotos.items():
                        if fila_r == fila:
                            celdas[_INDICE_CAMPO[campo]] = valor
                libro.escribir_fila(nombre, fila, tuple(celdas))
        else:
            codigo_hoja = nombre.removeprefix("APU ")
            escribir_hoja_apu_sintetica(
                libro,
                nombre,
                codigo=codigo_hoja,
                **variantes.get(codigo_hoja, {}),
            )

    return libro.bytes()


_TOPE_DE_ESPERA_NS = 30 * 1_000_000_000


def _esperar_archivo(ruta: Path) -> None:
    """Sondea cada 10 ms hasta que exista `ruta`, con tope de 30 s (vive en el hijo)."""
    limite = time.monotonic_ns() + _TOPE_DE_ESPERA_NS
    while not ruta.exists() and time.monotonic_ns() < limite:
        time.sleep(0.01)


def _resultado_de_prueba(inicio: int) -> ResultadoAnalisis:
    return ResultadoAnalisis(
        errores=(),
        preparacion={
            "formato": 1,
            "pid": os.getpid(),
            "inicio": inicio,
            "fin": time.time_ns(),
        },
        filas_leidas=0,
        filas_validas=0,
        filas_rechazadas=0,
    )


def trabajo_de_prueba(
    importacion_id: UUID,
    contenido: bytes,
    insumos: Mapping[str, str],
) -> ResultadoAnalisis:
    """Trabajo inyectable del ejecutor (TKT-015b): `contenido` es la orden a ejecutar.

    Órdenes: `anotar`, `bloquear:<ruta>`, `morir:<ruta>`, `fallar`, `avance:<ruta>` y
    `avance-desordenado:<ruta>`. De nivel de módulo para que `spawn` lo importe en el hijo.
    """
    inicio = time.time_ns()
    orden, _, argumento = contenido.decode().partition(":")
    if orden == "anotar":
        return _resultado_de_prueba(inicio)
    if orden == "bloquear":
        _esperar_archivo(Path(argumento))
        return _resultado_de_prueba(inicio)
    if orden == "morir":
        _esperar_archivo(Path(argumento))
        os._exit(1)
    if orden == "fallar":
        raise ValueError("fallo de prueba")
    if orden in ("avance", "avance-desordenado"):
        pasos = ((1, 5), (3, 5)) if orden == "avance" else ((3, 5), (1, 5))
        for leidas, totales in pasos:
            notificar_avance(importacion_id, leidas, totales)
        _esperar_archivo(Path(argumento))
        return _resultado_de_prueba(inicio)
    raise ValueError(f"orden de prueba desconocida: {orden!r}")


def liberar(ruta: Path) -> None:
    """Crea el archivo que espera `trabajo_de_prueba` y lo deja seguir."""
    ruta.write_text("liberado", encoding="utf-8")
