"""Ayudantes compartidos por las pruebas de definición de `tools/tests` (TKT-009b).

`test_definicion_ci.py` y `test_definicion_dependabot.py` comprueban texto YAML con mutantes: toman un texto válido,
lo estropean de una forma concreta y exigen que la comprobación se ponga en rojo y por la razón esperada. Lo que
ambos módulos hacían igual vive aquí, una sola vez.

* `_sangria`  columnas de sangría de una línea.
* `sustituir`  aplica un mutante de texto exactamente una vez.
* `exigir_rojo` y `exigir_rojo_en_todos`  exigen que la comprobación detecte el mutante.
* `localizar_bash` y `ejecutar_en_bash`  corren el `run:` de un paso con `bash` sobre un árbol temporal y programas de
  mentira, para comprobar lo que el paso *hace* y no solo lo que dice su texto.

Una comprobación recibe la entrada ya preparada y devuelve la lista de problemas que encuentra. Si la entrada del
mutante es texto y la comprobación trabaja sobre otra forma (por ejemplo, el texto dividido en trabajos), el módulo
que llama pasa `preparar`, que convierte el texto en esa forma antes de comprobar.
"""

from __future__ import annotations

import functools
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Any


def _sangria(linea: str) -> int:
    return len(linea) - len(linea.lstrip(" "))


def sustituir(texto: str, viejo: str, nuevo: str) -> str:
    """Mutante sobre el texto entero: cambia `viejo` por `nuevo` exactamente una vez, o falla.

    Un mutante que no se puede aplicar, o que no cambia nada, daría un verde engañoso.
    """
    if texto.count(viejo) != 1:
        raise AssertionError(
            f"el mutante no es aplicable: {viejo!r} aparece {texto.count(viejo)} veces en el texto"
        )
    mutante = texto.replace(viejo, nuevo)
    if mutante == texto:
        raise AssertionError(f"el mutante no cambia nada: {viejo!r} y {nuevo!r} son iguales")
    return mutante


def exigir_rojo(
    caso: unittest.TestCase,
    comprobacion: Callable[..., list[str]],
    entrada: Any,
    fragmento: str | None = None,
    *,
    preparar: Callable[[Any], Any] | None = None,
) -> list[str]:
    """El mutante `entrada` debe poner `comprobacion` en rojo y, si se da `fragmento`, por la razón esperada: algún problema lo menciona."""
    problemas = comprobacion(entrada if preparar is None else preparar(entrada))
    caso.assertNotEqual(
        problemas, [], "el mutante debía poner la comprobación en rojo y pasó en verde"
    )
    if fragmento is not None:
        caso.assertTrue(
            any(fragmento in problema for problema in problemas),
            f"el rojo no es por la razón esperada: ningún problema menciona {fragmento!r}: {problemas}",
        )
    return problemas


def exigir_rojo_en_todos(
    caso: unittest.TestCase,
    comprobacion: Callable[..., list[str]],
    casos: dict,
    fragmento: str | None = None,
    fragmentos: dict[str, str] | None = None,
    *,
    preparar: Callable[[Any], Any] | None = None,
) -> None:
    """Corre `exigir_rojo` por cada mutante de `casos`. El fragmento esperado sale, por orden, de `fragmentos[descripcion]`,
    del `(entrada, fragmento)` del propio caso o del `fragmento` común. `fragmentos` no puede nombrar un mutante que no existe."""
    fragmentos = fragmentos or {}
    caso.assertEqual(set(fragmentos) - set(casos), set(), "fragmentos para mutantes que no existen")
    for descripcion, valor in casos.items():
        entrada, propio = valor if isinstance(valor, tuple) else (valor, fragmento)
        with caso.subTest(mutante=descripcion):
            exigir_rojo(
                caso, comprobacion, entrada, fragmentos.get(descripcion, propio), preparar=preparar
            )


# ---------------------------------------------------------------------------------------------------------
# Ejecución del `run:` de un paso con bash
# ---------------------------------------------------------------------------------------------------------

# Lo que bash debe poder hacer para que el árbol temporal sirva: mostrar su versión, abrir una ruta de Windows escrita
# con barras (`C:/Users/...`) y encontrar las herramientas. El `bash.exe` de WSL imprime su versión pero no abre esa ruta.
_PRUEBA_DE_BASH = (
    'echo "$BASH_VERSION"; test -d "$1" && echo directorio-legible; '
    "command -v grep env mkdir > /dev/null && echo herramientas"
)


def _directorios_de_herramientas(bash: str) -> list[str]:
    """Los directorios que `bash` necesita en el `PATH` para encontrar `env`, `grep` y `mkdir`: el suyo y, en Git for Windows, `usr/bin`."""
    carpeta = Path(bash).resolve().parent
    candidatos = [carpeta, carpeta.parent / "usr" / "bin"]
    return [str(c) for c in candidatos if c.is_dir()]


def _entorno(
    bash: str, antes_en_path: list[str], extra: dict[str, str] | None = None
) -> dict[str, str]:
    entorno = dict(os.environ)
    entorno["PATH"] = os.pathsep.join(
        [*antes_en_path, *_directorios_de_herramientas(bash), entorno.get("PATH", "")]
    )
    entorno.update(extra or {})
    return entorno


def _motivo_de_rechazo(bash: str) -> str | None:
    """`None` si `bash` sirve para las pruebas de comportamiento; si no, por qué no."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporal:
        try:
            resultado = subprocess.run(
                [bash, "-c", _PRUEBA_DE_BASH, "bash", Path(temporal).as_posix()],
                capture_output=True,
                timeout=60,
                env=_entorno(bash, []),
            )
        except (OSError, subprocess.SubprocessError) as error:
            return f"no se pudo ejecutar ({error})"
    # Bytes, no texto: un candidato que no escribe UTF-8 (el lanzador de WSL imprime UTF-16) no debe romper el hilo lector.
    salida = resultado.stdout.decode("utf-8", errors="replace")
    lineas = salida.split()
    if "�" in salida:
        return "no imprime su versión (su salida no es UTF-8 legible): no es bash"
    if not lineas or lineas[0] in ("directorio-legible", "herramientas"):
        return "no imprime su versión (`$BASH_VERSION` vacío): no es bash"
    if "directorio-legible" not in lineas:
        return "no abre rutas de Windows escritas con barras (¿es el bash de WSL?)"
    if "herramientas" not in lineas:
        return "no encuentra `env`, `grep` o `mkdir`"
    return None


def _candidatos_de_bash() -> list[str]:
    candidatos: list[str] = []
    explicito = os.environ.get("CIMENTA_BASH")
    if explicito:
        candidatos.append(explicito)
    del_path = shutil.which("bash")
    if del_path:
        candidatos.append(del_path)
    git = shutil.which("git")
    raices = [Path(git).resolve().parent.parent] if git else []
    for variable in ("ProgramFiles", "ProgramW6432", "ProgramFiles(x86)"):
        if os.environ.get(variable):
            raices.append(Path(os.environ[variable]) / "Git")
    raices.append(Path("C:/Program Files/Git"))
    for raiz in raices:
        candidatos += [str(raiz / "bin" / "bash.exe"), str(raiz / "usr" / "bin" / "bash.exe")]
    return list(dict.fromkeys(candidatos))


@functools.cache
def localizar_bash() -> str:
    """La ruta de un `bash` utilizable. Si no hay ninguno, **falla** (`AssertionError`) con el motivo de cada candidato:
    el pipeline prohíbe saltar pruebas, y un paso sin ejecutar no es un paso comprobado.

    Orden: la variable `CIMENTA_BASH` (si está, debe servir), el `bash` del `PATH` y las rutas típicas de Git for Windows.
    En Windows el `bash` del `PATH` puede ser el de WSL; por eso cada candidato debe imprimir `$BASH_VERSION`, abrir una
    ruta de Windows con barras y encontrar `env`, `grep` y `mkdir`.
    """
    explicito = os.environ.get("CIMENTA_BASH")
    rechazados: list[str] = []
    for candidato in _candidatos_de_bash():
        if candidato != explicito and not os.path.isfile(candidato):
            continue
        motivo = _motivo_de_rechazo(candidato)
        if motivo is None:
            return candidato
        rechazados.append(f"  {candidato}: {motivo}")
        if candidato == explicito:
            break
    raise AssertionError(
        "No hay un bash utilizable para ejecutar los pasos del pipeline. Instala Git for Windows o define CIMENTA_BASH "
        "con la ruta de un bash que abra rutas como `C:/Users/...`. Candidatos probados:\n"
        + ("\n".join(rechazados) if rechazados else "  (ninguno existe)")
    )


def _escribir(raiz: Path, ruta: str, texto: str, *, ejecutable: bool = False) -> None:
    destino = raiz / ruta
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(texto.encode("utf-8"))  # siempre LF: un CRLF rompería el guion en bash
    if ejecutable:
        destino.chmod(destino.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def ejecutar_en_bash(
    run: str,
    *,
    archivos: dict[str, str],
    ejecutables: dict[str, str] | None = None,
    en_path: dict[str, str] | None = None,
    entorno: dict[str, str] | None = None,
) -> tuple[int, str]:
    """Ejecuta `run` como lo haría `shell: bash` en GitHub (`bash --noprofile --norc -eo pipefail`) y devuelve `(código, salida)`.

    * `archivos`: ruta relativa -> texto, en un árbol temporal que es el directorio de trabajo.
    * `ejecutables`: igual, pero con permiso de ejecución (el `mmdc` de mentira de `.github/mermaid/node_modules/.bin`).
    * `en_path`: nombre -> guion, programas de mentira que van los primeros del `PATH` (el `uvx` de mentira).
    * `entorno`: variables extra. `RUNNER_TEMP` y `GITHUB_WORKSPACE` ya apuntan al árbol temporal.

    La salida mezcla la estándar y la de error. Las rutas se pasan a bash en formato POSIX con barras (`C:/...`).
    """
    bash = localizar_bash()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temporal:
        raiz = Path(temporal)
        arbol, binarios, runner = raiz / "arbol", raiz / "bin", raiz / "runner"
        for carpeta in (arbol, binarios, runner):
            carpeta.mkdir()
        for ruta, texto in archivos.items():
            _escribir(arbol, ruta, texto)
        for ruta, texto in (ejecutables or {}).items():
            _escribir(arbol, ruta, texto, ejecutable=True)
        for nombre, texto in (en_path or {}).items():
            _escribir(binarios, nombre, texto, ejecutable=True)
        _escribir(raiz, "paso.sh", run + "\n")
        variables = {
            "RUNNER_TEMP": runner.as_posix(),
            "GITHUB_WORKSPACE": arbol.as_posix(),
            **(entorno or {}),
        }
        resultado = subprocess.run(
            [bash, "--noprofile", "--norc", "-eo", "pipefail", (raiz / "paso.sh").as_posix()],
            capture_output=True,
            timeout=120,
            cwd=arbol,
            env=_entorno(bash, [str(binarios)], variables),
        )
    salida = (resultado.stdout + resultado.stderr).decode("utf-8", errors="replace")
    return resultado.returncode, salida.replace("\r\n", "\n")
