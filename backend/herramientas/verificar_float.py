"""Regla 1 de CLAUDE.md (TKT-004): ningún float en una anotación de cimenta/*/dominio/ ni de tipos_base/.

Uso, desde backend/:  uv run python -m herramientas.verificar_float [--raiz DIR]
Termina con 0 sin hallazgos, 1 con hallazgos y 2 si no encontró ningún archivo que revisar.
Decimal(0.1) lo marca Ruff con RUF032. Un archivo que no se puede leer o analizar da un
hallazgo `ruta:línea: motivo` y código 1: un archivo ilegible nunca da verde.

Límites conocidos (PA-T14). No detecta: alias como `Tasa = float` ni `type X = float`,
`TypeVar(bound=float)` ni límites de parámetros de tipo PEP 695, `b.float`, valores por
omisión como `x=0.5`, `float(x)` en el cuerpo ni comentarios `# type:`. Falso positivo con
`Literal["float"]` y `Annotated[int, "float"]`.
"""

from __future__ import annotations

import argparse
import ast
import sys
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

PATRONES = ("cimenta/*/dominio/**/*.py", "tipos_base/**/*.py")


@dataclass(frozen=True)
class Hallazgo:
    ruta: Path
    linea: int
    donde: str


def archivos_a_revisar(raiz: Path) -> list[Path]:
    return sorted({ruta for patron in PATRONES for ruta in raiz.glob(patron)})


def _menciona_float(anotacion: ast.expr) -> bool:
    for nodo in ast.walk(anotacion):
        if isinstance(nodo, ast.Name) and nodo.id == "float":
            return True
        if (
            isinstance(nodo, ast.Attribute)
            and nodo.attr == "float"
            and isinstance(nodo.value, ast.Name)
            and nodo.value.id == "builtins"
        ):
            return True
        if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
            try:
                interior = ast.parse(nodo.value, mode="eval").body
            except SyntaxError:
                continue
            if _menciona_float(interior):
                return True
    return False


def _anotaciones(arbol: ast.Module) -> Iterator[tuple[ast.expr, str]]:
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.FunctionDef | ast.AsyncFunctionDef):
            args = nodo.args
            for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs, args.vararg, args.kwarg):
                if arg is not None and arg.annotation is not None:
                    yield arg.annotation, f"el parámetro {arg.arg} de {nodo.name}"
            if nodo.returns is not None:
                yield nodo.returns, f"el retorno de {nodo.name}"
        elif isinstance(nodo, ast.AnnAssign):
            yield nodo.annotation, f"la anotación de {ast.unparse(nodo.target)}"


def buscar_float(codigo: str, ruta: Path) -> list[Hallazgo]:
    arbol = ast.parse(codigo, filename=str(ruta))
    return [
        Hallazgo(ruta, anotacion.lineno, donde)
        for anotacion, donde in _anotaciones(arbol)
        if _menciona_float(anotacion)
    ]


def main(argv: Sequence[str] | None = None) -> int:
    lector = argparse.ArgumentParser(prog="verificar_float", description=__doc__)
    lector.add_argument("--raiz", type=Path, default=Path("."))
    opciones = lector.parse_args(argv)
    archivos = archivos_a_revisar(opciones.raiz)
    if not archivos:
        print(
            f"verificar_float: ningún archivo que revisar bajo {opciones.raiz.resolve()}; "
            "se ejecuta desde backend/",
            file=sys.stderr,
        )
        return 2
    hallazgos: list[Hallazgo] = []
    ilegibles = 0
    for ruta in archivos:
        try:
            codigo = ruta.read_text(encoding="utf-8-sig")
            hallazgos.extend(buscar_float(codigo, ruta))
        except OSError as error:
            ilegibles += 1
            motivo = error.strerror or type(error).__name__
            print(f"{ruta.as_posix()}:1: no se pudo leer el archivo: {motivo[:100]}")
        except (SyntaxError, UnicodeDecodeError) as error:
            ilegibles += 1
            linea = getattr(error, "lineno", None) or 1
            motivo = getattr(error, "msg", None) or getattr(error, "reason", None) or str(error)
            print(f"{ruta.as_posix()}:{linea}: no se pudo analizar el archivo: {str(motivo)[:100]}")
    for h in hallazgos:
        print(f"{h.ruta.as_posix()}:{h.linea}: float prohibido en {h.donde} (regla 1 de CLAUDE.md)")
    print(
        f"verificar_float: archivos revisados: {len(archivos)}; hallazgos: {len(hallazgos) + ilegibles}"
    )
    return 1 if hallazgos or ilegibles else 0


if __name__ == "__main__":
    raise SystemExit(main())
