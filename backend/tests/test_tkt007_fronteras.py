"""Firma, interfaz y fronteras del asiento (TKT-007, fila 4): TC-35 (AST), TC-41 a TC-45.

Sin Docker: ningún caso pide una *fixture* que abra la base. TC-44 y TC-45 reutilizan el esquema
de TKT-005: cada violación se escribe en una copia del árbol bajo `tmp_path`, nunca en el árbol que
se revisa, y `lint-imports` se identifica por el `id` del contrato.

Los símbolos de producción se importan **dentro** de cada caso: así cada uno falla por sí solo con
el `ImportError` del símbolo pedido y la recolección no se cae.

TC-44 y TC-45 nacen en verde (el diseño lo prevé): los contratos `grafo-identidad` y
`solo-por-interfaz` ya existen y ya rechazan cualquier importación indebida, esté o no el módulo
de destino. Lo que demuestra que dependen de algo son los mutantes de `impl.md`: quitar
`cimenta.auditoria` de la lista de módulos protegidos, o dejar a `auditoria` entre los
importadores permitidos de `identidad`.
"""

import ast
import inspect
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple

import pytest

BACKEND = Path(__file__).resolve().parents[1]
AUDITORIA = BACKEND / "cimenta" / "auditoria"
ENTORNO = {**os.environ, "PYTHONIOENCODING": "utf-8", "COLUMNS": "250"}
IGNORAR = shutil.ignore_patterns("__pycache__", "*.pyc", ".mypy_cache", ".import_linter_cache")
# `import-linter` no tiene `__main__`: se invoca el mismo punto de entrada que `lint-imports`.
LINTER = "from importlinter.cli import lint_imports_command; lint_imports_command()"
RESUMEN = re.compile(r"Contracts: (\d+) kept, (\d+) broken")
APLICACION_DE_AUDITORIA = "cimenta/auditoria/aplicacion/x_tkt007.py"
APLICACION_DE_COMPRAS = "cimenta/compras/aplicacion/x_tkt007.py"
VERBOS_QUE_CONFIRMAN = {"commit", "rollback", "begin", "flush"}


class Corrida(NamedTuple):
    codigo: int
    salida: str


@pytest.fixture
def copia(tmp_path: Path) -> Path:
    """Copia de lo que `lint-imports` necesita: configuración, módulos, tipos base y herramientas."""
    destino = tmp_path / "copia"
    destino.mkdir()
    shutil.copy(BACKEND / "pyproject.toml", destino / "pyproject.toml")
    for paquete in ("cimenta", "tipos_base", "herramientas"):
        shutil.copytree(BACKEND / paquete, destino / paquete, ignore=IGNORAR)
    return destino


def escribir(ruta: Path, texto: str) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(texto, encoding="utf-8", newline="\n")


def correr_linter(cwd: Path, *contratos: str) -> Corrida:
    argumentos = [argumento for c in contratos for argumento in ("--contract", c)]
    proceso = subprocess.run(
        [sys.executable, "-c", LINTER, "--no-cache", *argumentos],
        cwd=cwd,
        env=ENTORNO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )
    return Corrida(proceso.returncode, proceso.stdout + proceso.stderr)


def contratos_cumplidos_y_rotos(corrida: Corrida) -> tuple[int, int]:
    resumen = RESUMEN.search(corrida.salida)
    assert resumen, corrida.salida
    return int(resumen.group(1)), int(resumen.group(2))


def afirmar_contrato_roto(corrida: Corrida) -> None:
    """El único contrato pedido terminó roto: código 1 y `0 kept, 1 broken`."""
    assert corrida.codigo == 1, corrida.salida
    assert contratos_cumplidos_y_rotos(corrida) == (0, 1), corrida.salida


def archivos_de(*carpetas: str) -> list[Path]:
    """Los `.py` de `cimenta/auditoria/<carpeta>/` del árbol real; todos los de auditoria sin argumentos."""
    raices = [AUDITORIA / carpeta for carpeta in carpetas] or [AUDITORIA]
    return sorted(archivo for raiz in raices for archivo in raiz.rglob("*.py"))


def modulos_importados(archivo: Path) -> Iterator[str]:
    """Nombre completo de cada módulo que el archivo importa, con los relativos ya resueltos."""
    # El paquete del archivo: su ruta sin el nombre del módulo (`__init__` incluido).
    paquete = list(archivo.relative_to(BACKEND).with_suffix("").parts[:-1])
    for nodo in ast.walk(ast.parse(archivo.read_text(encoding="utf-8"), filename=str(archivo))):
        if isinstance(nodo, ast.Import):
            for nombre in nodo.names:
                yield nombre.name
        elif isinstance(nodo, ast.ImportFrom):
            if nodo.level:
                base = paquete[: len(paquete) - (nodo.level - 1)]
                modulo = ".".join([*base, *(nodo.module.split(".") if nodo.module else [])])
            else:
                modulo = nodo.module or ""
            yield modulo
            for nombre in nodo.names:
                yield f"{modulo}.{nombre.name}"


# --------------------------------------------------------------------------- TC-35 (AST)


def test_tkt007_ca02_ningun_servicio_llama_a_commit() -> None:
    """TC-35 · CA-2 esc. 3 · regla 8 — ningún archivo de aplicacion/ ni infraestructura/ confirma ni deshace."""
    archivos = archivos_de("aplicacion", "infraestructura")
    nombres = {archivo.name for archivo in archivos}
    # Anti-verde vacío: sin los archivos del diseño, el recorrido no examinaría nada.
    assert {"asentar.py", "repositorio.py", "modelos.py"} <= nombres, sorted(nombres)

    llamadas = [
        f"{archivo.relative_to(BACKEND)}:{nodo.lineno} llama a .{nodo.func.attr}()"
        for archivo in archivos
        for nodo in ast.walk(ast.parse(archivo.read_text(encoding="utf-8"), filename=str(archivo)))
        if isinstance(nodo, ast.Call)
        and isinstance(nodo.func, ast.Attribute)
        and nodo.func.attr in VERBOS_QUE_CONFIRMAN
    ]
    assert llamadas == []


# --------------------------------------------------------------------------- TC-41 a TC-43


def test_tkt007_ca04_firma_sin_sesion_ni_correlacion() -> None:
    """TC-41 · CA-4 esc. 3 — asentar_denegacion no recibe la sesión web ni la correlación."""
    from cimenta.auditoria.interfaz import asentar_denegacion

    parametros = list(inspect.signature(asentar_denegacion).parameters.values())

    assert [p.name for p in parametros] == [
        "sesion_bd",
        "usuario_id",
        "ocurrido_en",
        "motivo",
        "datos",
    ]
    assert parametros[0].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert [p.kind for p in parametros[1:]] == [inspect.Parameter.KEYWORD_ONLY] * 4
    assert [p.default for p in parametros] == [inspect.Parameter.empty] * 5


def test_tkt007_ca08_firma_de_asentar() -> None:
    """TC-43 (complemento) · CA-8 esc. 1 — asentar tiene la firma del diseño: la sesión primero y el resto por nombre."""
    from cimenta.auditoria.interfaz import asentar

    parametros = list(inspect.signature(asentar).parameters.values())

    assert [p.name for p in parametros] == [
        "sesion_bd",
        "accion",
        "entidad_tipo",
        "entidad_id",
        "usuario_id",
        "ocurrido_en",
        "motivo",
        "regla_negocio",
        "obra_id",
        "datos_antes",
        "datos_despues",
    ]
    assert parametros[0].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert [p.kind for p in parametros[1:]] == [inspect.Parameter.KEYWORD_ONLY] * 10
    obligatorios = [p.name for p in parametros if p.default is inspect.Parameter.empty]
    assert obligatorios == [
        "sesion_bd",
        "accion",
        "entidad_tipo",
        "entidad_id",
        "usuario_id",
        "ocurrido_en",
    ]
    opcionales = {p.name: p.default for p in parametros if p.default is not inspect.Parameter.empty}
    assert opcionales == dict.fromkeys(
        ["motivo", "regla_negocio", "obra_id", "datos_antes", "datos_despues"]
    )


def test_tkt007_ca04_sustituible_con_monkeypatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-42 · CA-4 esc. 4 — otro módulo llama a asentar_denegacion por atributo de la interfaz y se puede sustituir."""
    from cimenta.auditoria import interfaz
    from cimenta.auditoria.interfaz import asentar_denegacion as original

    llamadas: list[dict[str, object]] = []

    def falsa(*args: object, **kwargs: object) -> str:
        llamadas.append({"args": args, "kwargs": kwargs})
        return "asiento-falso"

    def otro_modulo() -> object:
        # Así lo usa TKT-006: por el atributo del módulo, no con `from … import` al cargarse.
        from cimenta.auditoria import interfaz as auditoria

        return auditoria.asentar_denegacion(
            "sesion",  # type: ignore[arg-type]  # cadenas a propósito: se prueba la sustitución
            usuario_id="ana",  # type: ignore[arg-type]
            ocurrido_en="T0",  # type: ignore[arg-type]
            motivo="ROL_INSUFICIENTE",
            datos={},
        )

    monkeypatch.setattr(interfaz, "asentar_denegacion", falsa)
    resultado = otro_modulo()

    assert resultado == "asiento-falso"
    assert original is not falsa
    assert llamadas == [
        {
            "args": ("sesion",),
            "kwargs": {
                "usuario_id": "ana",
                "ocurrido_en": "T0",
                "motivo": "ROL_INSUFICIENTE",
                "datos": {},
            },
        }
    ]


def test_tkt007_ca08_funciones_desde_la_interfaz() -> None:
    """TC-43 · CA-8 esc. 1 — asentar, asentar_denegacion y AccionBitacora salen de cimenta.auditoria.interfaz."""
    from cimenta.auditoria import interfaz
    from cimenta.auditoria.dominio.asiento import AccionBitacora as del_dominio
    from cimenta.auditoria.interfaz import AccionBitacora, asentar, asentar_denegacion

    assert {"AccionBitacora", "asentar", "asentar_denegacion"} <= set(interfaz.__all__)
    assert callable(asentar)
    assert callable(asentar_denegacion)
    assert AccionBitacora is del_dominio
    assert AccionBitacora.DENEGAR.value == "DENEGAR"
    assert len(AccionBitacora) == 22


# --------------------------------------------------------------------------- TC-44 y TC-45


def test_tkt007_ca08_auditoria_no_importa_modulos(copia: Path) -> None:
    """TC-44 · CA-8 esc. 2 — auditoria no puede importar a ningún otro módulo: lo rompe grafo-identidad."""
    escribir(copia / APLICACION_DE_AUDITORIA, "import cimenta.identidad.interfaz\n")

    corrida = correr_linter(copia, "grafo-identidad")

    afirmar_contrato_roto(corrida)
    assert "x_tkt007" in corrida.salida, corrida.salida


def test_tkt007_ca08_ningun_archivo_de_auditoria_importa_otro_modulo() -> None:
    """TC-44 · CA-8 esc. 2 — en el árbol real, ningún .py de cimenta/auditoria/ importa cimenta.<otro>."""
    archivos = archivos_de()
    # Anti-verde vacío: el recorrido examina al menos el dominio que ya existe.
    assert BACKEND / "cimenta" / "auditoria" / "dominio" / "asiento.py" in archivos

    ajenos = sorted(
        f"{archivo.relative_to(BACKEND)} importa {modulo}"
        for archivo in archivos
        for modulo in modulos_importados(archivo)
        if modulo.split(".")[0] == "cimenta"
        and modulo not in {"cimenta", "cimenta.auditoria"}
        and not modulo.startswith("cimenta.auditoria.")
    )
    assert ajenos == []


def test_tkt007_ca08_otro_modulo_no_importa_sus_repositorios(copia: Path) -> None:
    """TC-45 · CA-8 esc. 3, CA-R3 — otro módulo no importa infraestructura de auditoria: lo rompe solo-por-interfaz."""
    sin_violar = correr_linter(copia)
    assert sin_violar.codigo == 0, sin_violar.salida
    assert contratos_cumplidos_y_rotos(sin_violar) == (15, 0), sin_violar.salida

    escribir(
        copia / APLICACION_DE_COMPRAS,
        "import cimenta.auditoria.infraestructura.repositorio\n",
    )
    corrida = correr_linter(copia, "solo-por-interfaz")

    afirmar_contrato_roto(corrida)
    assert "x_tkt007" in corrida.salida, corrida.salida
