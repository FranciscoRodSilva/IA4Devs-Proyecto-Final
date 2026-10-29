#!/usr/bin/env python3
"""Verificador de escenarios sin test (ADR-012, TKT-009c).

Estado: completo y enganchado al trabajo `herramientas` de `.github/workflows/ci.yml`, que lo ejecuta en cada pull
request y le pasa `--activas-base` con el `historias_activas.txt` de la base del PR cuando la base lo tiene.

Uso, desde la raíz del repositorio:
    python tools/verificar_escenarios.py [--raiz ruta] [--activas-base ruta]
"""
from __future__ import annotations

import argparse
import io
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

# tools/verificar_escenarios.py → tools/ → raíz del repositorio
RAIZ_DEL_REPOSITORIO = Path(__file__).resolve().parent.parent

PATRON_HDU = re.compile(r"^(?:test_)?hdu(\d{3})_esc(\d{2,})(?=$|[_\s·])")
PATRON_FUNDACION = re.compile(r"^(?:test_)?tkt\d{3}[a-z]?_car?\d+_esc\d+(?=$|[_\s·])")


@dataclass(frozen=True)
class Escenario:
    historia: str  # "HDU-002"
    numero: int
    titulo: str
    fase: int  # 1 o 2
    retirado_por: str | None  # "TKT-069" o None


@dataclass(frozen=True)
class NombreDeTest:
    archivo: str  # ruta relativa con /
    linea: int
    nombre: str


class EntradaInvalida(Exception):
    """La entrada está mal formada: el verificador termina en 2."""


@dataclass(frozen=True)
class Hecho:
    """Una línea del informe: etiqueta exacta (`FALTA`, `PENDIENTE`, `RETIRADO` o `ERROR`) y su texto."""

    etiqueta: str
    texto: str


@dataclass(frozen=True)
class Informe:
    """Resultado de `clasificar`: los hechos en orden de descubrimiento y los recuentos del resumen final."""

    hechos: tuple[Hecho, ...]
    total: int
    exigidos: int
    cubiertos: int
    faltan: int
    pendientes: int
    retirados: int
    tests_hdu: int
    tests_fundacion: int


# Los dos patrones de `tools/verificar_docs.py`, copiados a propósito (ver el diseño de TKT-009c).
_PATRON_HISTORIA = re.compile(r"^## (HDU-\d{3}) · ")
_PATRON_ESCENARIO = re.compile(r"^\*\*Escenario (\d+): (.*)\*\*$")
_PATRON_FILA_HDU = re.compile(r"^\|\s*(HDU-[0-9]{3})\s*\|")
_PATRON_RETIRO = re.compile(r"retirado por (TKT-[0-9]{3})")
_PATRON_ACTIVA = re.compile(r"HDU-[0-9]{3}")


def _celdas(linea: str) -> list[str]:
    return [celda.strip() for celda in linea.strip().strip("|").split("|")]


def _fases_del_conjunto(lineas: list[str]) -> dict[str, int]:
    """Columna `Fase` de cada historia, leída solo de la tabla de la sección «## El conjunto».

    Las demás tablas del documento (dependencias, por ejemplo) también tienen filas que empiezan por
    «| HDU-001 |»; por eso solo se mira dentro de esa sección.
    """
    # La tabla principal es la primera tabla de la sección, la de cabecera «| # | Historia | … | Fase |».
    # Las tablas que vienen después en la misma sección («Complejidad fijada…») no cuentan.
    estado = "fuera"  # "fuera" · "buscar" (cabecera) · "filas" · "fin"
    indice_fase = 0
    fases: dict[str, int] = {}
    for linea in lineas:
        if linea.startswith("## "):
            estado = "buscar" if linea.strip() == "## El conjunto" else "fuera"
            continue
        if estado == "fuera":
            continue
        if estado == "buscar":
            if not linea.startswith("|"):
                continue
            celdas = _celdas(linea)
            estado = "filas" if "Fase" in celdas else "fin"
            indice_fase = celdas.index("Fase") if "Fase" in celdas else 0
            continue
        if estado == "filas":
            if not linea.startswith("|"):
                estado = "fin"
                continue
            coincide = _PATRON_FILA_HDU.match(linea)
            if coincide is None:
                continue  # la línea separadora «|---|»
            celdas = _celdas(linea)
            if len(celdas) <= indice_fase:
                raise EntradaInvalida(f"la fila de «El conjunto» no tiene columna Fase: «{linea.strip()}»")
            fases[coincide.group(1)] = 2 if celdas[indice_fase] == "2" else 1
    return fases


def _partir_titulo(titulo: str) -> tuple[str, bool, str | None]:
    """Devuelve (título sin las marcas de fase y de retiro, marca «fase 2» presente, TKT de retiro o None).

    Solo mira los segmentos del título: una mención de retiro en el cuerpo de la historia no cuenta.
    """
    segmentos = titulo.split(" · ")
    marca_fase_2 = "fase 2" in segmentos
    retiro: str | None = None
    conservados: list[str] = []
    for segmento in segmentos:
        coincide = _PATRON_RETIRO.fullmatch(segmento)
        if coincide is not None:
            retiro = retiro or coincide.group(1)
        elif segmento not in ("fase 1", "fase 2"):
            conservados.append(segmento)
    return " · ".join(conservados), marca_fase_2, retiro


def leer_historias(texto: str) -> dict[str, list[Escenario]]:
    """Lee las historias y sus escenarios. Fase: 2 si el título tiene el segmento «fase 2», o si la columna
    `Fase` de la historia vale 2; en otro caso 1. Retiro: segmento «retirado por TKT-NNN» del título.
    Una sección de historia sin fila en «El conjunto» es `EntradaInvalida`.
    """
    lineas = texto.splitlines()
    fases = _fases_del_conjunto(lineas)

    brutos: dict[str, list[tuple[int, str]]] = {}
    actual: str | None = None
    for linea in lineas:
        if linea.startswith("## "):
            coincide = _PATRON_HISTORIA.match(linea)
            actual = coincide.group(1) if coincide else None
            if actual is not None:
                if actual in brutos:
                    raise EntradaInvalida(f"{actual} tiene dos secciones en el documento de historias")
                brutos[actual] = []
            continue
        if actual is None:
            continue
        coincide = _PATRON_ESCENARIO.match(linea.rstrip())
        if coincide is not None:
            brutos[actual].append((int(coincide.group(1)), coincide.group(2)))

    historias: dict[str, list[Escenario]] = {}
    for historia, escenarios in brutos.items():
        if historia not in fases:
            raise EntradaInvalida(f"{historia} no tiene fila en la tabla «El conjunto»")
        lista: list[Escenario] = []
        for numero, titulo_bruto in escenarios:
            titulo, marca_fase_2, retiro = _partir_titulo(titulo_bruto)
            fase = 2 if marca_fase_2 or fases[historia] == 2 else 1
            lista.append(Escenario(historia, numero, titulo, fase, retiro))
        historias[historia] = lista
    return historias


def leer_activas(texto: str) -> tuple[frozenset[str], bool]:
    """Lee `historias_activas.txt`: líneas `HDU-NNN`, la línea exacta `fase 2`, comentarios y vacías.

    Cualquier otra línea es `EntradaInvalida` y el mensaje la nombra con su número.
    """
    activas: set[str] = set()
    fase_2 = False
    for numero, linea in enumerate(texto.splitlines(), start=1):
        if linea.strip() == "" or linea.startswith("#"):
            continue
        if _PATRON_ACTIVA.fullmatch(linea):
            activas.add(linea)
        elif linea == "fase 2":
            fase_2 = True
        else:
            raise EntradaInvalida(
                f"línea {numero} de historias_activas.txt: «{linea}» no es HDU-NNN, «fase 2», comentario ni vacía"
            )
    return frozenset(activas), fase_2


_TEST_PYTHON = re.compile(r"^\s*def (test_\w+)\s*\(")
_TEST_TYPESCRIPT = re.compile(r"(?<![\w.$])(?:it|test|describe)\(\s*([\"'`])(.*?)\1")

# (carpeta, patrones de archivo, lector de nombres). Ver A-8 en el diseño de TKT-009c.
_FUENTES_DE_TESTS = (
    ("backend/tests", ("test_*.py",), "python"),
    ("frontend/src", ("*.test.ts", "*.test.tsx"), "typescript"),
    ("frontend/scripts", ("*.test.ts", "*.test.tsx"), "typescript"),
    ("frontend/e2e", ("*.spec.ts",), "typescript"),
)


def _nombres_python(texto: str, archivo: str) -> list[NombreDeTest]:
    encontrados: list[NombreDeTest] = []
    for numero, linea in enumerate(texto.splitlines(), start=1):
        coincide = _TEST_PYTHON.match(linea)
        if coincide is not None:
            encontrados.append(NombreDeTest(archivo, numero, coincide.group(1)))
    return encontrados


def _lineas_con_codigo(texto: str) -> list[tuple[int, str]]:
    """Pares (número de línea, texto) de lo que no es comentario. Límite de A-8: un comentario al final de una
    línea de código no se descarta; solo se descartan las líneas que empiezan por un comentario y los bloques
    `/* … */`, aunque abran y cierren en líneas distintas. Lo que viene tras el cierre de un bloque sí se lee.
    """
    visibles: list[tuple[int, str]] = []
    en_bloque = False
    for numero, linea in enumerate(texto.splitlines(), start=1):
        if en_bloque:
            cierre = linea.find("*/")
            if cierre == -1:
                continue
            en_bloque = False
            linea = linea[cierre + 2 :]
        else:
            inicio = linea.lstrip()
            if inicio.startswith("//") or inicio.startswith("*"):
                continue
            if inicio.startswith("/*"):
                cierre = inicio.find("*/", 2)
                if cierre == -1:
                    en_bloque = True
                    continue
                linea = inicio[cierre + 2 :]
        visibles.append((numero, linea))
    return visibles


def _nombres_typescript(texto: str, archivo: str) -> list[NombreDeTest]:
    encontrados: list[NombreDeTest] = []
    for numero, linea in _lineas_con_codigo(texto):
        for coincide in _TEST_TYPESCRIPT.finditer(linea):
            encontrados.append(NombreDeTest(archivo, numero, coincide.group(2)))
    return encontrados


_LECTORES = {"python": _nombres_python, "typescript": _nombres_typescript}


def recolectar_tests(raiz: Path) -> list[NombreDeTest]:
    """Lee los nombres de test de A-8, con ruta relativa con «/», línea y nombre. Salta `node_modules`."""
    encontrados: list[NombreDeTest] = []
    for carpeta, patrones, lector in _FUENTES_DE_TESTS:
        directorio = raiz / carpeta
        if not directorio.is_dir():
            continue
        for patron in patrones:
            for ruta in directorio.rglob(patron):
                relativa = ruta.relative_to(raiz)
                if "node_modules" in relativa.parts or not ruta.is_file():
                    continue
                texto = _leer(ruta, raiz)
                encontrados.extend(_LECTORES[lector](texto, relativa.as_posix()))
    return sorted(encontrados, key=lambda t: (t.archivo, t.linea))


def clasificar(
    historias: dict[str, list[Escenario]],
    activas: frozenset[str],
    fase_2: bool,
    tests: list[NombreDeTest],
    base: tuple[frozenset[str], bool] | None,
) -> Informe:
    """Implementa CA-6, CA-7 y CA-8 (ADR-012). Sin E/S: recibe lo leído y devuelve el informe.

    Un escenario es exigido si su historia está activa, no está retirado y su fase es 1, o es 2 con la fase 2
    iniciada. Una historia activa que no existe en el documento es `EntradaInvalida` (código 2).
    """
    inexistentes = sorted(h for h in activas if h not in historias)
    if inexistentes:
        raise EntradaInvalida(
            f"historias_activas.txt nombra {', '.join(inexistentes)}, que no existe en el documento de historias"
        )

    hechos: list[Hecho] = []
    cubiertos_por_test: set[tuple[str, int]] = set()
    tests_hdu = 0
    tests_fundacion = 0
    for test in tests:
        ubicacion = f"{test.archivo}:{test.linea} · {test.nombre}"
        coincide = PATRON_HDU.match(test.nombre)
        if coincide is not None:
            historia = f"HDU-{coincide.group(1)}"
            numero = int(coincide.group(2))
            if historia not in historias:
                hechos.append(
                    Hecho("ERROR", f"{ubicacion} nombra una historia que no existe (hdu{coincide.group(1)})")
                )
            elif numero not in {e.numero for e in historias[historia]}:
                hechos.append(
                    Hecho("ERROR", f"{ubicacion} nombra un escenario que no existe ({historia} esc. {coincide.group(2)})")
                )
            else:
                cubiertos_por_test.add((historia, numero))
                tests_hdu += 1
        elif PATRON_FUNDACION.match(test.nombre) is not None:
            tests_fundacion += 1

    total = exigidos = cubiertos = faltan = pendientes = retirados = 0
    for historia, escenarios in historias.items():
        activa = historia in activas
        sin_ticket = 0  # escenarios no retirados de una historia inactiva
        for escenario in escenarios:
            total += 1
            etiqueta = f"{historia} esc. {escenario.numero}"
            if escenario.retirado_por is not None:
                retirados += 1
                hechos.append(Hecho("RETIRADO", f"{etiqueta} · {escenario.retirado_por}"))
                continue
            if not activa:
                pendientes += 1
                sin_ticket += 1
                continue
            if escenario.fase == 2 and not fase_2:
                pendientes += 1
                hechos.append(Hecho("PENDIENTE", f"{etiqueta} · fase 2 sin iniciar"))
                continue
            exigidos += 1
            if (historia, escenario.numero) in cubiertos_por_test:
                cubiertos += 1
            else:
                faltan += 1
                hechos.append(Hecho("FALTA", f"{etiqueta} · {escenario.titulo}"))
        if sin_ticket:
            hechos.append(Hecho("PENDIENTE", f"{historia} · {sin_ticket} escenarios · historia sin ticket en curso"))

    if base is not None:
        base_activas, base_fase_2 = base
        for historia in sorted(base_activas - activas):
            hechos.append(
                Hecho("ERROR", f"{historia} salió de tools/historias_activas.txt: una historia no sale nunca (ADR-012)")
            )
        if base_fase_2 and not fase_2:
            hechos.append(
                Hecho("ERROR", "la línea «fase 2» salió de tools/historias_activas.txt: no sale nunca (ADR-012)")
            )

    return Informe(
        hechos=tuple(hechos),
        total=total,
        exigidos=exigidos,
        cubiertos=cubiertos,
        faltan=faltan,
        pendientes=pendientes,
        retirados=retirados,
        tests_hdu=tests_hdu,
        tests_fundacion=tests_fundacion,
    )


ANCHO_ETIQUETA = 11  # «FALTA», «PENDIENTE», «RETIRADO» y «ERROR» van seguidos de relleno hasta esta columna
ETIQUETAS_QUE_FALLAN = frozenset({"FALTA", "ERROR"})


def _nombre_para_humanos(ruta: Path, raiz: Path | None) -> str:
    """Ruta relativa a `raiz` con «/» si `ruta` está bajo ella; si no, solo el nombre (p. ej. `--activas-base`)."""
    if raiz is not None:
        try:
            return ruta.relative_to(raiz).as_posix()
        except ValueError:
            pass
    return ruta.name


def _leer(ruta: Path, raiz: Path | None = None) -> str:
    """Lee un archivo en UTF-8. Un archivo que no es UTF-8 es una entrada mal formada que nombra su ruta."""
    try:
        return ruta.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise EntradaInvalida(f"{_nombre_para_humanos(ruta, raiz)} no está en UTF-8: {error}") from error


def _informe(raiz: Path, activas_base: Path | None) -> Informe:
    """Lee la entrada bajo `raiz` y clasifica. Cualquier entrada mal formada es `EntradaInvalida`."""
    ruta_documento = raiz / "docs" / "04-historias-usuario.md"
    if not ruta_documento.is_file():
        raise EntradaInvalida(f"no existe docs/04-historias-usuario.md bajo {raiz}")
    ruta_activas = raiz / "tools" / "historias_activas.txt"
    if not ruta_activas.is_file():
        raise EntradaInvalida("no existe tools/historias_activas.txt: el verificador no adivina qué historias están activas")

    historias = leer_historias(_leer(ruta_documento, raiz))
    activas, fase_2 = leer_activas(_leer(ruta_activas, raiz))

    base: tuple[frozenset[str], bool] | None = None
    if activas_base is not None and activas_base.is_file():
        try:
            base = leer_activas(_leer(activas_base))
        except EntradaInvalida as error:
            raise EntradaInvalida(f"en la base del PR ({activas_base.name}): {error}") from error

    return clasificar(historias, activas, fase_2, recolectar_tests(raiz), base)


def _imprimir(informe: Informe) -> None:
    for hecho in informe.hechos:
        print(f"{hecho.etiqueta:<{ANCHO_ETIQUETA}}{hecho.texto}")
    print(
        f"Escenarios: {informe.total} · exigidos {informe.exigidos} · cubiertos {informe.cubiertos} · "
        f"faltan {informe.faltan} · pendientes {informe.pendientes} · retirados {informe.retirados} · "
        f"tests HDU {informe.tests_hdu} · tests de fundación {informe.tests_fundacion}"
    )


def _salida_utf8() -> None:
    """Fuerza UTF-8 en la consola de Windows. Solo toca un `TextIOWrapper`: un `StringIO` de una captura no se toca."""
    for flujo in (sys.stdout, sys.stderr):
        if isinstance(flujo, io.TextIOWrapper):
            flujo.reconfigure(encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    """Código 0 sin `FALTA` ni `ERROR`; 1 si hay alguno; 2 si la entrada está mal formada (ADR-012)."""
    _salida_utf8()
    parser = argparse.ArgumentParser(description="Verifica que cada escenario exigido tenga su test (ADR-012).")
    parser.add_argument("--raiz", type=Path, default=RAIZ_DEL_REPOSITORIO, help="raíz del repositorio")
    parser.add_argument(
        "--activas-base", type=Path, default=None, help="historias_activas.txt del PR base; si no existe, no se compara"
    )
    argumentos = parser.parse_args(argv)

    try:
        informe = _informe(argumentos.raiz, argumentos.activas_base)
    except EntradaInvalida as error:
        print(f"entrada mal formada: {error}", file=sys.stderr)
        return 2

    _imprimir(informe)
    return 1 if any(hecho.etiqueta in ETIQUETAS_QUE_FALLAN for hecho in informe.hechos) else 0


if __name__ == "__main__":
    sys.exit(main())
