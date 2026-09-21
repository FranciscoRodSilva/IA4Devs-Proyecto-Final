#!/usr/bin/env python3
"""Extrae los diagramas Mermaid de la documentación y los valida.

Un diagrama con error de sintaxis se renderiza en GitHub como un bloque de
error, no como un diagrama. Dado que la documentación es el entregable de la
Entrega 1, eso no puede llegar a la rama principal.

Dos modos:

    python tools/extraer_mermaid.py               # genera una página HTML
    python tools/extraer_mermaid.py --json        # vuelca los diagramas a JSON

La página generada parsea cada diagrama con Mermaid en el navegador y escribe
el resultado en su título ("TODO OK" o "FALLOS: n") y en el cuerpo. Ábrela
sirviéndola por HTTP; con `file://` los navegadores bloquean el módulo.

    python -m http.server 8000 --directory <carpeta de salida>

En integración continua conviene sustituirla por `@mermaid-js/mermaid-cli`,
que hace lo mismo sin navegador. Este script existe para poder verificar en
local sin instalar Node.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

EXCLUIR = {'Doc de contexto', 'node_modules', '.git', '.venv', 'dist'}
BLOQUE = re.compile(r'```mermaid\n(.*?)```', re.S)

PLANTILLA = """<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>Validación Mermaid</title>
<style>body{font-family:ui-monospace,monospace;padding:2rem;line-height:1.5}</style>
<script type="module">
import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs';
mermaid.initialize({ startOnLoad: false });
const bloques = __BLOQUES__;
const resultados = [];
for (const b of bloques) {
  try { await mermaid.parse(b.code); resultados.push({ ...b, ok: true }); }
  catch (e) { resultados.push({ ...b, ok: false, error: String(e?.message ?? e) }); }
}
const fallidos = resultados.filter(r => !r.ok);
document.getElementById('salida').textContent = JSON.stringify({
  total: resultados.length,
  ok: resultados.length - fallidos.length,
  fallidos: fallidos.map(f => ({ archivo: f.file, linea: f.line, error: f.error })),
}, null, 2);
document.title = fallidos.length ? ('FALLOS: ' + fallidos.length) : 'TODO OK';
</script></head><body><pre id="salida">ejecutando…</pre></body></html>"""


def recolectar(raiz: str) -> list[dict]:
    bloques = []
    for base, dirs, nombres in os.walk(raiz):
        dirs[:] = [d for d in dirs if d not in EXCLUIR]
        for n in sorted(nombres):
            if not n.endswith('.md'):
                continue
            ruta = os.path.join(base, n)
            with open(ruta, encoding='utf-8') as f:
                texto = f.read()
            for m in BLOQUE.finditer(texto):
                bloques.append({
                    'file': os.path.relpath(ruta, raiz).replace('\\', '/'),
                    'line': texto[:m.start()].count('\n') + 1,
                    'code': m.group(1),
                })
    return bloques


def main() -> int:
    raiz_por_defecto = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raiz', default=raiz_por_defecto)
    parser.add_argument('--salida', default=None,
                        help='archivo de salida (por omisión, junto al script)')
    parser.add_argument('--json', action='store_true', help='vuelca JSON en lugar de HTML')
    args = parser.parse_args()

    raiz = os.path.abspath(args.raiz)
    bloques = recolectar(raiz)
    print(f'{len(bloques)} diagramas encontrados')
    for b in bloques:
        primera = b['code'].splitlines()[0][:40] if b['code'].strip() else '(vacío)'
        print(f"  {b['file']}:{b['line']}  {primera}")

    if args.json:
        destino = args.salida or os.path.join(raiz_por_defecto, 'tools', 'mermaid.json')
        with open(destino, 'w', encoding='utf-8') as f:
            json.dump(bloques, f, ensure_ascii=False, indent=2)
    else:
        destino = args.salida or os.path.join(raiz_por_defecto, 'tools', 'mermaid-check.html')
        html = PLANTILLA.replace('__BLOQUES__', json.dumps(bloques, ensure_ascii=False))
        with open(destino, 'w', encoding='utf-8') as f:
            f.write(html)

    print(f'\nEscrito: {destino}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
