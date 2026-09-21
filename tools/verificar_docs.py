#!/usr/bin/env python3
"""Verificación de la documentación de CIMENTA.

Tres comprobaciones que no existen como herramienta de terceros y que el
proyecto necesita porque su documentación es el entregable:

1. Enlaces relativos entre documentos.
2. Anclas internas (#seccion), reproduciendo el algoritmo de GitHub.
3. Consistencia de identificadores: RN, RNF, PA, F, HDU, TKT, ADR e invariantes,
   más la aritmética de story points y el conteo de escenarios.

Uso:
    python tools/verificar_docs.py            # desde la raíz del repositorio
    python tools/verificar_docs.py --raiz .   # o indicando la raíz

Devuelve código de salida 1 si encuentra algún problema, para que falle el
pipeline. Los diagramas Mermaid se validan aparte: ver extraer_mermaid.py.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import unicodedata
import urllib.parse
from collections import defaultdict

EXCLUIR = {'Doc de contexto', 'node_modules', '.git', '.venv', 'dist'}
problemas: list[str] = []
avisos: list[str] = []


def documentos(raiz: str) -> dict[str, str]:
    """Devuelve {ruta relativa: contenido} de los documentos versionados."""
    out = {}
    for base, dirs, nombres in os.walk(raiz):
        dirs[:] = [d for d in dirs if d not in EXCLUIR]
        for n in nombres:
            if n.endswith('.md') or n == 'llms.txt':
                p = os.path.join(base, n)
                with open(p, encoding='utf-8') as f:
                    out[os.path.relpath(p, raiz)] = f.read()
    return out


# --------------------------------------------------------------- 1. enlaces
ENLACE = re.compile(r'\[([^\]]*)\]\(([^)\s]+)\)')
VALLA = re.compile(r'```.*?```', re.S)


def verificar_enlaces(raiz: str, docs: dict[str, str]) -> int:
    comprobados = 0
    for rel, texto in docs.items():
        for m in ENLACE.finditer(texto):
            destino = m.group(2)
            if destino.startswith(('http://', 'https://', 'mailto:', '#')):
                continue
            ruta = destino.split('#')[0]
            if not ruta:
                continue
            comprobados += 1
            absoluta = os.path.normpath(
                os.path.join(raiz, os.path.dirname(rel), urllib.parse.unquote(ruta)))
            if not os.path.exists(absoluta):
                problemas.append(f'Enlace roto · {rel} → {destino}')
    return comprobados


# ---------------------------------------------------------------- 2. anclas
ENCABEZADO = re.compile(r'^(#{1,6})\s+(.*)$', re.M)


def ancla(texto: str) -> str:
    """Reproduce el algoritmo de anclas de GitHub."""
    texto = re.sub(r'`([^`]*)`', r'\1', texto)
    texto = re.sub(r'\*\*([^*]*)\*\*', r'\1', texto)
    texto = re.sub(r'\*([^*]*)\*', r'\1', texto)
    texto = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', texto)
    out = []
    for ch in texto.strip().lower():
        if ch in ' \t-':
            out.append('-')
        elif unicodedata.category(ch)[0] in ('L', 'N'):
            out.append(ch)
    return ''.join(out)


def verificar_anclas(raiz: str, docs: dict[str, str]) -> int:
    anclas: dict[str, set[str]] = {}
    for rel, texto in docs.items():
        vistas: dict[str, int] = {}
        conjunto = set()
        for m in ENCABEZADO.finditer(VALLA.sub('', texto)):
            a = ancla(m.group(2))
            if a in vistas:
                vistas[a] += 1
                a = f'{a}-{vistas[a]}'
            else:
                vistas[a] = 0
            conjunto.add(a)
        anclas[os.path.normpath(os.path.join(raiz, rel))] = conjunto

    comprobados = 0
    for rel, texto in docs.items():
        for m in ENLACE.finditer(VALLA.sub('', texto)):
            destino = m.group(2)
            if destino.startswith(('http://', 'https://', 'mailto:')) or '#' not in destino:
                continue
            ruta, fragmento = destino.split('#', 1)
            fragmento = urllib.parse.unquote(fragmento)
            comprobados += 1
            objetivo = os.path.normpath(os.path.join(
                raiz, os.path.dirname(rel), urllib.parse.unquote(ruta))) if ruta \
                else os.path.normpath(os.path.join(raiz, rel))
            if objetivo not in anclas:
                problemas.append(f'Ancla hacia documento no analizado · {rel} → {destino}')
            elif fragmento not in anclas[objetivo]:
                problemas.append(f'Ancla inexistente · {rel} → {destino}')
    return comprobados


# --------------------------------------------------------- 3. identificadores
def verificar_identificadores(raiz: str, docs: dict[str, str]) -> dict[str, int]:
    prd = docs.get(os.path.join('docs', '01-descripcion-producto.md'), '')
    hdu = docs.get(os.path.join('docs', '04-historias-usuario.md'), '')
    tkt = docs.get(os.path.join('docs', '05-tickets-trabajo.md'), '')
    mod = docs.get(os.path.join('docs', '03-modelo-datos.md'), '')

    resumen = {}

    def citados(patron: str) -> dict[str, set[str]]:
        uso = defaultdict(set)
        for rel, texto in docs.items():
            for x in re.findall(patron, texto):
                uso[x].add(rel)
        return uso

    # Reglas de negocio
    rn_def = set(re.findall(r'\|\s*\*\*(RN-\d+)\*\*\s*\|', prd))
    for rn, donde in citados(r'\bRN-\d+\b').items():
        if rn not in rn_def:
            problemas.append(f'Regla inexistente citada: {rn} en {sorted(donde)}')
    numeros = sorted(int(r.split('-')[1]) for r in rn_def)
    if numeros and [n for n in range(1, max(numeros) + 1) if n not in numeros]:
        problemas.append('Huecos en la numeración de reglas de negocio')
    resumen['reglas'] = len(rn_def)

    # Requisitos no funcionales
    rnf_def = set(re.findall(r'\|\s*\*\*(RNF-\d+)\*\*\s*\|', prd))
    rnf_uso = citados(r'\bRNF-\d+\b')
    for rnf, donde in rnf_uso.items():
        if rnf not in rnf_def:
            problemas.append(f'Requisito no funcional inexistente citado: {rnf} en {sorted(donde)}')
    numeros = sorted(int(r.split('-')[1]) for r in rnf_def)
    if numeros and [n for n in range(1, max(numeros) + 1) if n not in numeros]:
        problemas.append('Huecos en la numeración de requisitos no funcionales')
    # Un requisito que solo aparece donde se declara no lo implementa nadie.
    for rnf in sorted(rnf_def):
        if rnf_uso[rnf] <= {os.path.join('docs', '01-descripcion-producto.md')}:
            avisos.append(f'{rnf} solo aparece en el PRD: ningún ticket lo recoge')
    resumen['requisitos no funcionales'] = len(rnf_def)

    # Preguntas al cliente
    pa_def = set(re.findall(r'\|\s*\*\*(PA-\d+)\*\*\s*\|', prd))
    for pa, donde in citados(r'\bPA-\d+\b').items():
        if pa not in pa_def:
            problemas.append(f'Pregunta inexistente citada: {pa} en {sorted(donde)}')
    resumen['preguntas'] = len(pa_def)

    # Funcionalidades
    f_def = set(re.findall(r'\*\*(F\d+\.\d+)\*\*', prd))
    for f, donde in citados(r'\bF\d+\.\d+\b').items():
        if f not in f_def:
            problemas.append(f'Funcionalidad inexistente citada: {f} en {sorted(donde)}')
    resumen['funcionalidades'] = len(f_def)

    # Historias
    hdu_def = set(re.findall(r'^## (HDU-\d{3}) · ', hdu, re.M))
    for h, donde in citados(r'\bHDU-\d{3}\b').items():
        if h not in hdu_def:
            problemas.append(f'Historia inexistente citada: {h} en {sorted(donde)}')
    resumen['historias'] = len(hdu_def)

    # Tickets: fichas completas y filas de tabla
    tkt_def = (re.findall(r'\*\*(TKT-\d{3})\*\*\s*\|', tkt)
               + re.findall(r'^### (TKT-\d{3}) · ', tkt, re.M))
    duplicados = {t for t in tkt_def if tkt_def.count(t) > 1}
    if duplicados:
        problemas.append(f'Tickets duplicados: {sorted(duplicados)}')
    tkt_set = set(tkt_def)
    for m in re.finditer(r'TKT-(\d{3})\s*…\s*TKT-(\d{3})', tkt):
        a, b = int(m.group(1)), int(m.group(2))
        faltan = [f'TKT-{n:03d}' for n in range(a, b + 1)
                  if f'TKT-{n:03d}' not in tkt_set]
        if faltan:
            problemas.append(f'Rango TKT-{a:03d}…TKT-{b:03d} cita tickets inexistentes: {faltan}')
    resumen['tickets'] = len(tkt_set)

    # ADRs
    adr_dir = os.path.join(raiz, 'docs', 'adr')
    if os.path.isdir(adr_dir):
        archivos = {n for n in os.listdir(adr_dir) if re.match(r'\d{8}-.*\.md$', n)}
        indice = set(re.findall(r'\((\d{8}-[a-z0-9-]+\.md)\)',
                                docs.get(os.path.join('docs', 'adr', 'README.md'), '')))
        for a in sorted(archivos - indice):
            problemas.append(f'ADR sin entrada en el índice: {a}')
        for a in sorted(indice - archivos):
            problemas.append(f'ADR en el índice pero sin archivo: {a}')
        resumen['adrs'] = len(archivos)

    # Invariantes
    inv_def = set(re.findall(r'^\|\s*(\d+)\s*\|', mod, re.M))
    patron_inv = re.compile(r'[Ii]nvariantes?[ \t]+((?:\d+)(?:(?:,[ \t]*|[ \t]+y[ \t]+)\d+)*)')
    for texto in docs.values():
        for m in patron_inv.finditer(texto):
            for num in re.findall(r'\d+', m.group(1)):
                if num not in inv_def:
                    problemas.append(f'Invariante inexistente citado: {num}')
    resumen['invariantes'] = len(inv_def)

    # Story points
    filas = re.findall(
        r'\| HDU-\d{3} \| \[[^\]]+\]\([^)]+\) \| [^|]+\| [^|]+\| [^|]+\| (\d+) \|', hdu)
    if filas:
        suma = sum(int(x) for x in filas)
        declarado = re.search(r'\*\*Total: (\d+) SP', hdu)
        if declarado and int(declarado.group(1)) != suma:
            problemas.append(
                f'Story points descuadrados: la tabla suma {suma}, se declara {declarado.group(1)}')
        resumen['story points'] = suma

    # Escenarios y su declaración en la Definition of Done
    cabeceras = [(m.start(), m.group(1)) for m in re.finditer(r'^## (HDU-\d{3}) · ', hdu, re.M)]
    cabeceras.append((len(hdu), None))
    total = 0
    for i in range(len(cabeceras) - 1):
        bloque = hdu[cabeceras[i][0]:cabeceras[i + 1][0]]
        nombre = cabeceras[i][1]
        nums = [int(x) for x in re.findall(r'\*\*Escenario (\d+): ', bloque)]
        total += len(nums)
        if nums != list(range(1, len(nums) + 1)):
            problemas.append(f'{nombre}: numeración de escenarios no contigua')
        dod = re.search(r'Cubre los (\d+) escenarios', bloque)
        if not dod:
            problemas.append(f'{nombre}: la Definition of Done no declara el número de escenarios')
        elif int(dod.group(1)) != len(nums):
            problemas.append(
                f'{nombre}: tiene {len(nums)} escenarios pero la DoD declara {dod.group(1)}')
    declarado = re.search(r'· (\d+) escenarios', hdu)
    if declarado and int(declarado.group(1)) != total:
        problemas.append(
            f'Escenarios descuadrados: hay {total}, se declaran {declarado.group(1)}')
    resumen['escenarios'] = total

    return resumen


def main() -> int:
    # La consola de Windows usa cp1252 por omisión y no sabe escribir ✓ ni ✗.
    # Sin esto el verificador revienta al imprimir el resultado, pase o no pase.
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, 'reconfigure'):
            flujo.reconfigure(encoding='utf-8', errors='replace')

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raiz', default=os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), help='raíz del repositorio')
    args = parser.parse_args()
    raiz = os.path.abspath(args.raiz)

    docs = documentos(raiz)
    print(f'Documentos analizados: {len(docs)}\n')

    n_enlaces = verificar_enlaces(raiz, docs)
    n_anclas = verificar_anclas(raiz, docs)
    resumen = verificar_identificadores(raiz, docs)

    print(f'  enlaces relativos  {n_enlaces:>5}')
    print(f'  anclas internas    {n_anclas:>5}')
    for k, v in resumen.items():
        print(f'  {k:<18} {v:>5}')

    print()
    if problemas:
        print(f'PROBLEMAS ({len(problemas)})')
        for p in problemas:
            print(f'  ✗ {p}')
    else:
        print('✓ Sin problemas.')
    for a in avisos:
        print(f'  · {a}')
    return 1 if problemas else 0


if __name__ == '__main__':
    sys.exit(main())
