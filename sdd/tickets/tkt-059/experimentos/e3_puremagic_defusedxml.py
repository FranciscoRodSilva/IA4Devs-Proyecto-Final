"""E-3 · puremagic y defusedxml se comportan como asume el detector (design.md, «Detección del tipo por los bytes», paso 3 y 4).

Ejecución: uv run --python 3.14 --with puremagic --with defusedxml python -I -X utf8 e3_puremagic_defusedxml.py
"""

import sys

import puremagic
from defusedxml.common import DTDForbidden, EntitiesForbidden, ExternalReferenceForbidden
from defusedxml.ElementTree import DefusedXMLParser

EXTENSIONES_DISENO = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".heic": "image/heic",
    ".heif": "image/heic",
    ".mp4": "video/mp4",
    ".pdf": "application/pdf",
}

MUESTRAS = {
    "JPEG": b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00" + b"\x00" * 64,
    "PNG": b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"\x00" * 64,
    "WebP": b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 64,
    "HEIC (ftypheic)": b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00mif1heic" + b"\x00" * 64,
    "MP4 (ftypisom)": b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2avc1mp41" + b"\x00" * 64,
    "PDF": b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< /Type /Catalog >>\nendobj\n" + b"\x00" * 64,
    "MZ (ejecutable)": b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00" + b"\x00" * 64 + b"PE\x00\x00",
    "ZIP": b"PK\x03\x04\x14\x00\x00\x00\x08\x00" + b"\x00" * 64,
}


class Destino:
    def __init__(self) -> None:
        self.eventos: list[str] = []

    def start(self, tag, attrib):
        self.eventos.append(tag)

    def end(self, tag):
        pass

    def data(self, data):
        pass

    def close(self):
        return None


def candidatas(cabecera: bytes) -> list[tuple[str, str]]:
    try:
        return [(c.extension, c.mime_type) for c in puremagic.magic_string(cabecera)]
    except (puremagic.PureError, puremagic.PureValueError) as e:  # type: ignore[attr-defined]
        print(f"    PureError: {e}")
        return []


def main() -> int:
    print("== puremagic.magic_string: candidatas en orden y resolución por EXTENSIONES_DISENO")
    print(f"  puremagic {getattr(puremagic, '__version__', '?')}")
    tabla_resultado: dict[str, str] = {}
    binarios_sin_tabla: list[str] = []
    for nombre, cab in MUESTRAS.items():
        lista = candidatas(cab)
        print(f"- {nombre}: {len(lista)} candidatas")
        for ext, mime in lista:
            print(f"    extension={ext!r} mime_type={mime!r}")
        primera = lista[0] if lista else None
        if primera:
            print(f"    PRIMERA extension={primera[0]!r} mime_type={primera[1]!r}")
        resuelto = next(((e, m) for e, m in lista if e in EXTENSIONES_DISENO), None)
        if resuelto:
            tabla_resultado[nombre] = f"{resuelto[0]} -> {EXTENSIONES_DISENO[resuelto[0]]}"
        else:
            tabla_resultado[nombre] = "fuera de EXTENSIONES_DISENO"
            if nombre != "MZ (ejecutable)" and nombre != "ZIP":
                binarios_sin_tabla.append(nombre)
        print(f"    resolucion con la tabla del diseno: {tabla_resultado[nombre]}")

    print("\n== Variantes de marca (comprobación adicional, no entran en el veredicto)")
    variantes = {
        "HEIC mif1": b"\x00\x00\x00\x18ftypmif1\x00\x00\x00\x00mif1heic" + b"\x00" * 64,
        "HEIC heix": b"\x00\x00\x00\x18ftypheix\x00\x00\x00\x00heixmif1" + b"\x00" * 64,
        "HEIC msf1": b"\x00\x00\x00\x18ftypmsf1\x00\x00\x00\x00msf1heic" + b"\x00" * 64,
        "MP4 mp42": b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 64,
        "MP4 M4V": b"\x00\x00\x00\x18ftypM4V \x00\x00\x00\x00M4V mp42isom" + b"\x00" * 64,
        "JPEG EXIF (FFD8FFE1)": b"\xff\xd8\xff\xe1\x00\x16Exif\x00\x00II*\x00" + b"\x00" * 64,
        "WebP VP8L": b"RIFF\x24\x00\x00\x00WEBPVP8L" + b"\x00" * 64,
    }
    for nombre, cab in variantes.items():
        lista = candidatas(cab)
        resuelto = next(((e, m) for e, m in lista if e in EXTENSIONES_DISENO), None)
        pri = f"{lista[0][0]}/{lista[0][1]}" if lista else "sin candidatas"
        res = f"{resuelto[0]} -> {EXTENSIONES_DISENO[resuelto[0]]}" if resuelto else "fuera de la tabla"
        print(f"  {nombre}: primera={pri} · tabla={res}")

    print("\n== DefusedXMLParser: DOCTYPE con entidades")
    doctype = b'<?xml version="1.0"?>\n<!DOCTYPE lolz [<!ENTITY lol "lol">]>\n<lolz>&lol;</lolz>'
    dest = Destino()
    parser = DefusedXMLParser(target=dest, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    lanzo_en_feed = None
    try:
        parser.feed(doctype)
        lanzo_en_feed = False
    except DTDForbidden as e:
        lanzo_en_feed = "DTDForbidden"
        print(f"  feed lanzo DTDForbidden: {e}")
    except (EntitiesForbidden, ExternalReferenceForbidden) as e:
        lanzo_en_feed = type(e).__name__
        print(f"  feed lanzo {type(e).__name__}: {e}")
    print(f"  lanza durante feed: {lanzo_en_feed}")
    dtd_en_feed_ok = lanzo_en_feed == "DTDForbidden"

    print("\n== DefusedXMLParser: SVG")
    svg = b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" width="10"><rect/></svg>'
    dest2 = Destino()
    parser2 = DefusedXMLParser(target=dest2, forbid_dtd=True, forbid_entities=True, forbid_external=True)
    parser2.feed(svg)
    print(f"  eventos start (sin close): {dest2.eventos}")
    svg_ok = bool(dest2.eventos) and dest2.eventos[0] == "{http://www.w3.org/2000/svg}svg"

    print("\n== RESUMEN E-3")
    for nombre, res in tabla_resultado.items():
        print(f"  {nombre}: {res}")
    binarios_ok = all(
        tabla_resultado[n] != "fuera de EXTENSIONES_DISENO"
        for n in ["JPEG", "PNG", "WebP", "HEIC (ftypheic)", "MP4 (ftypisom)", "PDF"]
    )
    print(f"  seis tipos binarios dan extension de la tabla: {binarios_ok}")
    print(f"  binarios sin tabla (requieren firma propia): {binarios_sin_tabla}")
    print(f"  MZ fuera de la tabla: {tabla_resultado['MZ (ejecutable)'] == 'fuera de EXTENSIONES_DISENO'}")
    print(f"  DOCTYPE lanza durante feed: {dtd_en_feed_ok}")
    print(f"  SVG entrega {{http://www.w3.org/2000/svg}}svg a start: {svg_ok}")
    ok = binarios_ok and dtd_en_feed_ok and svg_ok and tabla_resultado["MZ (ejecutable)"] == "fuera de EXTENSIONES_DISENO"
    print(f"VEREDICTO E-3 = {'OK' if ok else 'REVISAR'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
