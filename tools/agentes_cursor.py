"""Genera y verifica los agentes de Cursor a partir de los de Claude Code.

La fuente única es `.claude/agents/*.md`. Cursor lee también ese directorio, pero su
frontmatter es distinto: `model: haiku` o `model: sonnet` no son identificadores de Cursor, y
`tools`, `effort` y `skills` los ignora. Para que ninguna de las dos herramientas pierda
contexto, `.cursor/agents/` se genera desde la fuente y, en Cursor, tiene precedencia sobre
`.claude/agents/` cuando el nombre coincide.

Qué cambia en la traducción:

* `model` pasa a `composer-2.5[fast=false]`: Composer 2.5 sin la variante rápida.
* `readonly: true` solo para el agente que no tiene herramientas de escritura ni de consola.
* `tools`, `effort` y `skills` se descartan. Las convenciones que `skills` precargaba se
  convierten en una instrucción de lectura al principio del cuerpo, porque Cursor no precarga.
* El cuerpo se copia después de ese aviso. Solo cambian los enlaces relativos que salen de `.claude/`
  (`../skills/…`, `./`), para que sigan resolviendo desde `.cursor/agents/`.

Uso, desde la raíz del repositorio:

    python tools/agentes_cursor.py --generar     # reescribe .cursor/agents/
    python tools/agentes_cursor.py --verificar   # falla si .cursor/agents/ difiere de lo generado

Sin dependencias, como el resto de `tools/`.
"""
from __future__ import annotations

import os
import re
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORIGEN = os.path.join(RAIZ, ".claude", "agents")
DESTINO = os.path.join(RAIZ, ".cursor", "agents")

MODELO_CURSOR = "composer-2.5[fast=false]"
HERRAMIENTAS_DE_ESCRITURA = {"Write", "Edit", "Bash", "PowerShell"}


def separar(texto: str) -> tuple[dict[str, object], str]:
    """Parte un agente en su frontmatter y su cuerpo. El frontmatter solo admite `clave: valor` y listas de `- elemento`."""
    if not texto.startswith("---\n"):
        raise ValueError("el archivo no empieza por `---`")
    fin = texto.find("\n---\n", 4)
    if fin == -1:
        raise ValueError("el frontmatter no se cierra con `---`")
    campos: dict[str, object] = {}
    clave_lista: str | None = None
    for linea in texto[4:fin].split("\n"):
        if linea.startswith("  - ") and clave_lista is not None:
            lista = campos[clave_lista]
            assert isinstance(lista, list)
            lista.append(linea[4:].strip())
            continue
        clave, separador, valor = linea.partition(":")
        if not separador:
            raise ValueError(f"línea de frontmatter sin `:`: {linea!r}")
        clave = clave.strip()
        valor = valor.strip()
        if valor:
            campos[clave] = valor
            clave_lista = None
        else:
            campos[clave] = []
            clave_lista = clave
    return campos, texto[fin + 5 :]


def reencaminar_enlaces(cuerpo: str) -> str:
    """Los enlaces `../skills/` y `./` del original apuntan dentro de `.claude/`; desde `.cursor/agents/` hay que salir a él."""
    cuerpo = re.sub(r"\]\(\.\./(?!\.)", "](../../.claude/", cuerpo)
    return cuerpo.replace("](./)", "](../../.claude/agents/)")


def traducir(texto: str, nombre_archivo: str) -> str:
    """Devuelve el agente de Cursor equivalente al agente de Claude Code `texto`."""
    campos, cuerpo = separar(texto)
    for obligatorio in ("name", "description"):
        if not campos.get(obligatorio):
            raise ValueError(f"{nombre_archivo}: falta `{obligatorio}`")
    herramientas = {h.strip() for h in str(campos.get("tools", "")).split(",") if h.strip()}
    solo_lectura = not (herramientas & HERRAMIENTAS_DE_ESCRITURA)

    cabecera = ["---", f"name: {campos['name']}", f"description: {campos['description']}", f"model: {MODELO_CURSOR}"]
    if solo_lectura:
        cabecera.append("readonly: true")
    cabecera.append("---")

    aviso = [
        f"<!-- Generado por tools/agentes_cursor.py desde .claude/agents/{nombre_archivo}. No lo edites: cambia el original y vuelve a generar. -->",
        "",
    ]
    convenciones = campos.get("skills")
    if isinstance(convenciones, list) and convenciones:
        rutas = ", ".join(f"`.claude/skills/{c}/SKILL.md`" for c in convenciones)
        aviso += [f"> **Antes de empezar, lee {rutas}.** Cursor no precarga las convenciones de tu capa.", ""]

    return "\n".join(cabecera) + "\n\n" + "\n".join(aviso) + "\n" + reencaminar_enlaces(cuerpo.lstrip("\n"))


def esperados() -> dict[str, str]:
    """Nombre de archivo -> contenido que debería tener en `.cursor/agents/`."""
    resultado: dict[str, str] = {}
    for nombre in sorted(os.listdir(ORIGEN)):
        if not nombre.endswith(".md"):
            continue
        with open(os.path.join(ORIGEN, nombre), encoding="utf-8", newline="") as f:
            resultado[nombre] = traducir(f.read().replace("\r\n", "\n"), nombre)
    return resultado


def verificar() -> list[str]:
    """Problemas entre `.cursor/agents/` y lo que generaría `.claude/agents/`. Lista vacía si coinciden."""
    problemas: list[str] = []
    esperado = esperados()
    existentes = set(os.listdir(DESTINO)) if os.path.isdir(DESTINO) else set()
    for nombre, contenido in esperado.items():
        ruta = os.path.join(DESTINO, nombre)
        if nombre not in existentes:
            problemas.append(f".cursor/agents/{nombre} no existe: ejecuta `python tools/agentes_cursor.py --generar`")
            continue
        with open(ruta, encoding="utf-8", newline="") as f:
            if f.read().replace("\r\n", "\n") != contenido:
                problemas.append(f".cursor/agents/{nombre} difiere de .claude/agents/{nombre}: vuelve a generar")
    for nombre in sorted(existentes - set(esperado)):
        problemas.append(f".cursor/agents/{nombre} no tiene original en .claude/agents/")
    return problemas


def generar() -> list[str]:
    """Reescribe `.cursor/agents/` y devuelve los archivos escritos."""
    esperado = esperados()
    os.makedirs(DESTINO, exist_ok=True)
    for nombre in os.listdir(DESTINO):
        if nombre.endswith(".md") and nombre not in esperado:
            os.remove(os.path.join(DESTINO, nombre))
    for nombre, contenido in esperado.items():
        with open(os.path.join(DESTINO, nombre), "w", encoding="utf-8", newline="\n") as f:
            f.write(contenido)
    return sorted(esperado)


def main(argumentos: list[str]) -> int:
    if argumentos == ["--generar"]:
        escritos = generar()
        print(f"{len(escritos)} agentes de Cursor generados en .cursor/agents/")
        return 0
    if argumentos == ["--verificar"]:
        problemas = verificar()
        for problema in problemas:
            print(problema)
        if not problemas:
            print("Los agentes de Cursor coinciden con los de Claude Code.")
        return 1 if problemas else 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
