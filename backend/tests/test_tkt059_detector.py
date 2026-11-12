"""Detector de tipo por los bytes (TKT-059, fila 6): TC-25, TC-25b y TC-52.

El detector vive en `cimenta/archivos/infraestructura/detector_tipo.py` y se llama
`detectar_tipo(leer_rango, tamano)`. `leer_rango(inicio, fin)` devuelve los bytes `inicio..fin`,
ambos inclusivos. Estas pruebas usan un lector en memoria que:

- rechaza cualquier rango con inicio negativo, con inicio mayor que fin o con fin fuera de
  `tamano`; el rango queda en `fuera_de_rango` y la prueba falla aunque el detector silencie la
  excepción;
- cuenta los bytes entregados, que es lo que TC-52 acota.

Los símbolos de producción se importan dentro de cada prueba, no a nivel de módulo: mientras la
capa no existe, el rojo es un `ModuleNotFoundError` de `detector_tipo` y no un error de colección.

Dos expectativas siguen al diseño y no a la nota de la tarea:

- `MZ…` da `application/vnd.microsoft.portable-executable`. El paso 4 devuelve el tipo MIME de la
  primera candidata de `puremagic` con tipo no vacío, y `puremagic` reconoce `MZ` como `.exe` (E-3).
- El texto plano llega a `text/plain` solo si empieza por `<` y `expat` falla antes de la primera
  etiqueta (paso 3). Un texto que no empieza por `<` no tiene candidatas y da
  `application/octet-stream`.
"""

import io
import random
import struct
import time
import tracemalloc
import warnings
import zipfile
import zlib
from collections.abc import Callable
from typing import Any

import defusedxml.ElementTree
import openpyxl
import pytest

TIPO_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PARTE_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"
PARTE_XLSM = "application/vnd.ms-excel.sheet.macroEnabled.main+xml"
MIB = 1024 * 1024
COTA_LECTURA = 262_144
TAMANO_RELLENO = 26_000_000
SEMILLA_RELLENO = 20261111
LIMITE_SEGUNDOS = 5.0
EXPANSION_BOMBA_MIB = 64
PICO_MEMORIA = 16 * MIB  # tope de memoria que puede sostener el detector al leer una parte

LeerRango = Callable[[int, int], bytes]
DetectarTipo = Callable[[LeerRango, int], str]


class LectorContado:
    """`leer_rango` sobre bytes en memoria, con cuenta de lo entregado y control de rangos."""

    def __init__(self, contenido: bytes) -> None:
        self._contenido = contenido
        self.tamano = len(contenido)
        self.rangos: list[tuple[int, int]] = []
        self.fuera_de_rango: list[tuple[int, int]] = []

    @property
    def bytes_leidos(self) -> int:
        return sum(fin - inicio + 1 for inicio, fin in self.rangos)

    def __call__(self, inicio: int, fin: int) -> bytes:
        if not 0 <= inicio <= fin < self.tamano:
            self.fuera_de_rango.append((inicio, fin))
            raise AssertionError(f"rango {inicio}..{fin} fuera de un objeto de {self.tamano} bytes")
        self.rangos.append((inicio, fin))
        return self._contenido[inicio : fin + 1]


def _detectar(detectar_tipo: DetectarTipo, contenido: bytes) -> tuple[str, LectorContado]:
    lector = LectorContado(contenido)
    tipo = detectar_tipo(lector, lector.tamano)
    assert lector.fuera_de_rango == [], "el detector pidió rangos fuera del objeto"
    return tipo, lector


# ---------------------------------------------------------------------------------------------
# Muestras de imagen, video, PDF y XML
# ---------------------------------------------------------------------------------------------


def _jpeg_jfif() -> bytes:
    return b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00" + b"\x00" * 64


def _jpeg_exif() -> bytes:
    return b"\xff\xd8\xff\xe1\x00\x16Exif\x00\x00II*\x00" + b"\x00" * 64


def _png() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\rIHDR" + b"\x00" * 64


def _webp() -> bytes:
    return b"RIFF" + struct.pack("<I", 60) + b"WEBP" + b"VP8 " + b"\x00" * 56


def _ftyp(marca_mayor: bytes, compatibles: bytes) -> bytes:
    """Caja `ftyp` de ISO BMFF: tamaño, `ftyp`, marca mayor, versión menor y marcas compatibles."""
    caja = b"ftyp" + marca_mayor + b"\x00\x00\x00\x00" + compatibles
    return struct.pack(">I", 8 + len(caja)) + caja + b"\x00" * 64


def _pdf() -> bytes:
    return b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< /Type /Catalog >>\nendobj\n"


XML_CON_DECLARACION = (
    b'<?xml version="1.0" encoding="UTF-8"?>\n<comprobante version="4.0" total="12000.00"/>\n'
)
XML_SIN_DECLARACION = b'<comprobante version="4.0" total="12000.00"/>\n'
XML_CON_BOM = b"\xef\xbb\xbf" + XML_CON_DECLARACION
XML_CON_BLANCOS = b" \r\n\t" + XML_SIN_DECLARACION
XML_CON_DOCTYPE = (
    b'<?xml version="1.0"?>\n<!DOCTYPE comprobante [\n<!ELEMENT comprobante ANY>\n]>\n'
    b"<comprobante/>\n"
)
TEXTO_QUE_NO_ES_XML = b"< nota suelta, no es XML\n"  # empieza por `<` y falla antes de la etiqueta


def _svg(con_declaracion: bool) -> bytes:
    """SVG sin DOCTYPE, con un atributo de script que el detector no debe ejecutar ni admitir."""
    raiz = b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" onload="alert(1)"/>'
    if con_declaracion:
        return b'<?xml version="1.0" encoding="UTF-8"?>\n' + raiz + b"\n"
    return raiz + b"\n"


def _svg_con_hijos() -> bytes:
    """SVG con elementos hijos: lo que decide el tipo es la primera etiqueta, no la última."""
    raiz = b'<svg xmlns="http://www.w3.org/2000/svg"><g><rect width="1" height="1"/></g></svg>'
    return raiz + b"\n"


def _xml_con_svg_anidado() -> bytes:
    """XML cuya raíz no es `svg` pero lleva un `svg` dentro: el tipo lo da la raíz."""
    return b'<comprobante><svg xmlns="http://www.w3.org/2000/svg"/></comprobante>\n'


def _xml_con_entidades() -> bytes:
    """«Mil millones de risas»: diez niveles de diez referencias, sin expandir."""
    definiciones = ['<!ENTITY lol "lol">']
    for nivel in range(1, 10):
        definiciones.append(f'<!ENTITY lol{nivel} "' + f"&lol{nivel - 1};" * 10 + '">')
    cuerpo = "\n".join(definiciones)
    texto = '<?xml version="1.0"?>\n<!DOCTYPE lolz [\n' + cuerpo + "\n]>\n<lolz>&lol9;</lolz>\n"
    return texto.encode("utf-8")


# ---------------------------------------------------------------------------------------------
# Muestras ZIP y OOXML
# ---------------------------------------------------------------------------------------------

_CABECERA_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" '
    'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
)


def _content_types(*sobrescrituras: tuple[str, str]) -> bytes:
    partes = "".join(
        f'<Override PartName="{parte}" ContentType="{tipo}"/>' for parte, tipo in sobrescrituras
    )
    return (_CABECERA_CONTENT_TYPES + partes + "</Types>").encode("utf-8")


def _zip(entradas: dict[str, bytes], compresion: int = zipfile.ZIP_DEFLATED) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for nombre, datos in entradas.items():
            zf.writestr(nombre, datos, compress_type=compresion)
    return buf.getvalue()


def _xlsx_de_openpyxl() -> bytes:
    """Libro real de openpyxl: su `[Content_Types].xml` declara la parte de libro de `.xlsx`."""
    buf = io.BytesIO()
    libro = openpyxl.Workbook()
    libro.save(buf)
    return buf.getvalue()


def _xlsx_valido_minimo() -> bytes:
    """ZIP que cumple todo lo que el detector exige de un `.xlsx`, salvo el límite que cada caso
    de TC-52 rompe a propósito."""
    return _zip(
        {
            "[Content_Types].xml": _content_types(("/xl/workbook.xml", PARTE_XLSX)),
            "xl/workbook.xml": b"<workbook/>",
        }
    )


def _zip_sin_parte_de_libro() -> bytes:
    """`[Content_Types].xml` con hojas y estilos, pero sin la parte de libro de `.xlsx`."""
    return _zip(
        {
            "[Content_Types].xml": _content_types(
                (
                    "/xl/worksheets/sheet1.xml",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml",
                ),
                (
                    "/xl/styles.xml",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml",
                ),
            ),
            "xl/worksheets/sheet1.xml": b"<worksheet/>",
            "xl/styles.xml": b"<styleSheet/>",
        }
    )


def _zip_sin_content_types() -> bytes:
    return _zip({"xl/workbook.xml": b"<workbook/>", "docProps/app.xml": b"<Properties/>"})


def _content_types_sin_declaracion(doctype: str, *sobrescrituras: tuple[str, str]) -> bytes:
    """`[Content_Types].xml` que empieza por `doctype`. La declaración `<?xml ...?>` solo es válida
    al principio del documento, así que se quita de lo que genera `_content_types`."""
    declaracion = b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    cuerpo = _content_types(*sobrescrituras).removeprefix(declaracion)
    return doctype.encode("utf-8") + b"\n" + cuerpo


def _zip_con_doctype_en_content_types() -> bytes:
    """ZIP con DOCTYPE simple en `[Content_Types].xml` y la parte de libro de `.xlsx` declarada. Sin
    `forbid_dtd` el detector lo leería como `.xlsx`; con él, el DTD impide declarar nada y sale como
    ZIP genérico."""
    return _zip(
        {
            "[Content_Types].xml": _content_types_sin_declaracion(
                "<!DOCTYPE Types>", ("/xl/workbook.xml", PARTE_XLSX)
            ),
            "xl/workbook.xml": b"<workbook/>",
        }
    )


def _zip_con_entidad_en_content_types() -> bytes:
    """ZIP cuyo `[Content_Types].xml` define una entidad interna de dos niveles que expande a la parte
    de libro de `.xlsx`, y la usa en el `ContentType` del `Override`. Si el analizador expandiera
    entidades, declararía `.xlsx`; con `forbid_entities` sale como ZIP genérico, sin expandir nada."""
    doctype = (
        "<!DOCTYPE Types [\n"
        '<!ENTITY base "application/vnd.openxmlformats-officedocument.spreadsheetml">\n'
        '<!ENTITY tipo "&base;.sheet.main+xml">\n'
        "]>"
    )
    return _zip(
        {
            "[Content_Types].xml": _content_types_sin_declaracion(
                doctype, ("/xl/workbook.xml", "&tipo;")
            ),
            "xl/workbook.xml": b"<workbook/>",
        }
    )


def _xlsm() -> bytes:
    """Libro con macros: la parte principal lleva el tipo de `.xlsm`, no el de `.xlsx`."""
    return _zip(
        {
            "[Content_Types].xml": _content_types(
                ("/xl/workbook.xml", PARTE_XLSM),
                ("/xl/vbaProject.bin", "application/vnd.ms-office.vbaProject"),
            ),
            "xl/workbook.xml": b"<workbook/>",
            "xl/vbaProject.bin": b"\x00" * 32,
        }
    )


def _ejecutable_mz() -> bytes:
    return (
        b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00" + b"\x00" * 64 + b"PE\x00\x00"
    )


def _binario_no_reconocido() -> bytes:
    """Sin candidatas en `puremagic`: el detector no reconoce ninguna firma."""
    return bytes(range(16)) * 8


def _riff_avi() -> bytes:
    """Contenedor RIFF de video AVI: lleva `AVI ` donde un WebP lleva `WEBP` (bytes 8 a 11)."""
    return b"RIFF\x00\x00\x00\x00AVI LIST" + b"\x00" * 64


def _riff_wav() -> bytes:
    """Contenedor RIFF de audio WAV PCM: lleva `WAVE` donde un WebP lleva `WEBP`."""
    formato = struct.pack("<IHHIIHH", 16, 1, 1, 8000, 8000, 1, 8)
    return b"RIFF" + struct.pack("<I", 36 + 8) + b"WAVEfmt " + formato + b"data" + b"\x00" * 8


def _webp_con_chunk(chunk: bytes) -> bytes:
    return b"RIFF" + struct.pack("<I", 60) + b"WEBP" + chunk + b"\x00" * 56


def _xml_con_codificacion(codificacion: str) -> bytes:
    """Declaración XML con una codificación que `expat` no puede cargar o no soporta."""
    return f'<?xml version="1.0" encoding="{codificacion}"?><a/>'.encode("ascii")


def _zip_con_content_types_de_codificacion_desconocida() -> bytes:
    """ZIP con `xl/workbook.xml` cuyo `[Content_Types].xml` declara una codificación inexistente."""
    return _zip(
        {
            "[Content_Types].xml": b'<?xml version="1.0" encoding="bogus"?><Types/>',
            "xl/workbook.xml": b"<workbook/>",
        }
    )


# ---------------------------------------------------------------------------------------------
# Objetos grandes de TC-52
# ---------------------------------------------------------------------------------------------


def _libro_26_mb() -> bytes:
    """Libro de openpyxl con `xl/media/relleno.bin` de 26 000 000 bytes aleatorios, ZIP_STORED,
    añadido con `zipfile` en modo «a». La semilla fija hace el objeto reproducible."""
    buf = io.BytesIO()
    openpyxl.Workbook().save(buf)
    relleno = random.Random(SEMILLA_RELLENO).randbytes(TAMANO_RELLENO)
    with zipfile.ZipFile(buf, "a") as zf:
        zf.writestr("xl/media/relleno.bin", relleno, compress_type=zipfile.ZIP_STORED)
    return buf.getvalue()


def _directorio_declarado_2_mib() -> bytes:
    """El EOCD declara un directorio central de 2 MiB. El tramo declarado existe en el objeto
    (ceros), para que la única razón del rechazo sea el tamaño y no un rango fuera del objeto."""
    base = _xlsx_valido_minimo()
    _, _, _, _, _, _, cd_offset, _ = struct.unpack("<4sHHHHIIH", base[-22:])
    locales = base[:cd_offset]
    cd_declarado = 2 * MIB
    eocd = struct.pack("<4sHHHHIIH", b"PK\x05\x06", 0, 0, 2, 2, cd_declarado, len(locales), 0)
    return locales + b"\x00" * cd_declarado + eocd


def _parte_de_2_mib() -> bytes:
    """`[Content_Types].xml` de 2 MiB comprimidos (ZIP_STORED): válido como XML, excede el límite de
    parte. Un detector que lo leyera entero lo aceptaría como `.xlsx`."""
    relleno = b"<!--" + b"x" * (2 * MIB) + b"-->"
    contenido = _content_types(("/xl/workbook.xml", PARTE_XLSX)).replace(
        b"<Default", relleno + b"<Default", 1
    )
    return _zip(
        {"[Content_Types].xml": contenido, "xl/workbook.xml": b"<workbook/>"},
        compresion=zipfile.ZIP_STORED,
    )


def _parte_deflate_que_expande_64_mib() -> bytes:
    """`[Content_Types].xml` en ZIP_DEFLATED que comprime a unas decenas de KiB y expande a 64 MiB.

    Es XML válido con la parte de libro de `.xlsx` declarada, y el relleno es un comentario de 64 MiB.
    Se escribe por trozos de 1 MiB con `ZipFile.open(..., "w")`, para que construirlo no sostenga
    en memoria más que un trozo. El comprimido cabe de sobra en `MAXIMO_PARTE`; lo que lo excede es
    el descomprimido, y solo un tope en la descompresión lo detiene a tiempo.
    """
    cabeza, cola = (
        _content_types(("/xl/workbook.xml", PARTE_XLSX)).replace(b"<Default", b"@@", 1).split(b"@@")
    )
    trozo = b"x" * MIB
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        with zf.open("[Content_Types].xml", "w") as parte:
            parte.write(cabeza + b"<!--")
            for _ in range(EXPANSION_BOMBA_MIB):
                parte.write(trozo)
            parte.write(b"-->" + b"<Default" + cola)
        zf.writestr("xl/workbook.xml", b"<workbook/>", compress_type=zipfile.ZIP_DEFLATED)
    return buf.getvalue()


def _zip64() -> bytes:
    """Mismo libro válido, reescrito con registro EOCD64 y localizador ZIP64, y con los campos
    del EOCD clásico en `0xFFFF`/`0xFFFFFFFF`. Sin ZIP64 sería `.xlsx`."""
    base = _xlsx_valido_minimo()
    _, _, _, _, entradas, cd_size, cd_offset, _ = struct.unpack("<4sHHHHIIH", base[-22:])
    locales = base[:cd_offset]
    directorio = base[cd_offset : cd_offset + cd_size]
    inicio_eocd64 = len(locales) + len(directorio)
    eocd64 = struct.pack(
        "<4sQHHIIQQQQ", b"PK\x06\x06", 44, 45, 45, 0, 0, entradas, entradas, cd_size, cd_offset
    )
    localizador = struct.pack("<4sIQI", b"PK\x06\x07", 0, inicio_eocd64, 1)
    eocd = struct.pack("<4sHHHHIIH", b"PK\x05\x06", 0, 0, 0xFFFF, 0xFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0)
    return locales + directorio + eocd64 + localizador + eocd


# ---------------------------------------------------------------------------------------------
# TC-25 · la lista blanca se reconoce por los bytes
# ---------------------------------------------------------------------------------------------

CASOS_LISTA_BLANCA = [
    pytest.param(_jpeg_jfif(), "image/jpeg", id="jpeg-jfif"),
    pytest.param(_jpeg_exif(), "image/jpeg", id="jpeg-exif"),
    pytest.param(_png(), "image/png", id="png"),
    pytest.param(_webp(), "image/webp", id="webp"),
    pytest.param(_webp_con_chunk(b"VP8X"), "image/webp", id="webp-vp8x"),
    pytest.param(_webp_con_chunk(b"VP8L"), "image/webp", id="webp-vp8l"),
    pytest.param(_ftyp(b"heic", b"mif1heic"), "image/heic", id="heic-marca-heic"),
    pytest.param(_ftyp(b"heix", b"heixmif1"), "image/heic", id="heic-marca-heix"),
    pytest.param(_ftyp(b"mif1", b"mif1heic"), "image/heic", id="heic-marca-mif1"),
    pytest.param(_ftyp(b"msf1", b"msf1heic"), "image/heic", id="heic-marca-msf1"),
    pytest.param(_ftyp(b"isom", b"isomiso2avc1mp41"), "video/mp4", id="mp4-isom"),
    pytest.param(_ftyp(b"mp42", b"mp42isom"), "video/mp4", id="mp4-mp42"),
    pytest.param(_ftyp(b"M4V ", b"M4V mp42isom"), "video/mp4", id="mp4-m4v"),
    pytest.param(_pdf(), "application/pdf", id="pdf"),
    pytest.param(XML_CON_DECLARACION, "application/xml", id="xml-con-declaracion"),
    pytest.param(XML_SIN_DECLARACION, "application/xml", id="xml-sin-declaracion"),
    pytest.param(XML_CON_BOM, "application/xml", id="xml-con-bom-utf8"),
    pytest.param(XML_CON_BLANCOS, "application/xml", id="xml-con-blancos-iniciales"),
    pytest.param(_xlsx_de_openpyxl(), TIPO_XLSX, id="xlsx-openpyxl"),
]


@pytest.mark.parametrize(("contenido", "tipo"), CASOS_LISTA_BLANCA)
def test_tkt059_ca06_el_detector_reconoce_la_lista_blanca(contenido: bytes, tipo: str) -> None:
    """TC-25 · CA-6 · fila 6 — el tipo canónico de la lista blanca sale de los bytes."""
    from cimenta.archivos.infraestructura.detector_tipo import detectar_tipo

    detectado, _ = _detectar(detectar_tipo, contenido)
    assert detectado == tipo


# ---------------------------------------------------------------------------------------------
# TC-25b · lo no admitido se devuelve con su tipo exacto
# ---------------------------------------------------------------------------------------------

CASOS_NO_ADMITIDOS = [
    pytest.param(_svg(con_declaracion=True), "image/svg+xml", id="svg-con-declaracion"),
    pytest.param(_svg(con_declaracion=False), "image/svg+xml", id="svg-sin-declaracion"),
    pytest.param(_zip_sin_parte_de_libro(), "application/zip", id="zip-sin-parte-de-libro"),
    pytest.param(_zip_sin_content_types(), "application/zip", id="zip-sin-content-types"),
    pytest.param(_xlsm(), "application/zip", id="xlsm-con-macros"),
    pytest.param(
        _zip_con_doctype_en_content_types(),
        "application/zip",
        id="zip-con-doctype-en-content-types",
    ),
    pytest.param(
        _zip_con_entidad_en_content_types(),
        "application/zip",
        id="zip-con-entidad-en-content-types",
    ),
    pytest.param(_svg_con_hijos(), "image/svg+xml", id="svg-con-elementos-hijos"),
    pytest.param(_xml_con_svg_anidado(), "application/xml", id="xml-con-svg-anidado"),
    pytest.param(XML_CON_DOCTYPE, "application/xml-dtd", id="xml-con-doctype"),
    pytest.param(_xml_con_entidades(), "application/xml-dtd", id="xml-con-entidades"),
    pytest.param(
        _ejecutable_mz(), "application/vnd.microsoft.portable-executable", id="ejecutable-mz"
    ),
    pytest.param(TEXTO_QUE_NO_ES_XML, "text/plain", id="texto-que-no-es-xml"),
    pytest.param(_binario_no_reconocido(), "application/octet-stream", id="binario-sin-firma"),
    # Seguridad F001 / código F001: un archivo hostil no debe hacer lanzar a `expat` (LookupError,
    # ValueError); el rechazo de lo no admitido es un tipo, no una excepción.
    pytest.param(_xml_con_codificacion("bogus"), "text/plain", id="xml-codificacion-desconocida"),
    pytest.param(_xml_con_codificacion("shift_jis"), "text/plain", id="xml-codificacion-multibyte"),
    pytest.param(
        _zip_con_content_types_de_codificacion_desconocida(),
        "application/zip",
        id="zip-content-types-codificacion-desconocida",
    ),
    # Seguridad F003: `puremagic` ofrece `image/webp` como candidata de baja confianza para
    # cualquier RIFF; la lista blanca no puede aceptar lo que no lleva `WEBP` en los bytes 8 a 11.
    pytest.param(_riff_avi(), "application/octet-stream", id="riff-avi-no-es-webp"),
    pytest.param(_riff_wav(), "application/octet-stream", id="riff-wav-no-es-webp"),
]


@pytest.mark.parametrize(("contenido", "tipo"), CASOS_NO_ADMITIDOS)
def test_tkt059_ca06_el_detector_rechaza_lo_no_admitido(contenido: bytes, tipo: str) -> None:
    """TC-25b · CA-6 · fila 6 — lo no admitido sale con su tipo exacto, sin expandir entidades
    ni aceptar un ZIP sin la parte de libro, y en menos de cinco segundos."""
    from cimenta.archivos.infraestructura.detector_tipo import detectar_tipo

    inicio = time.perf_counter()
    detectado, _ = _detectar(detectar_tipo, contenido)
    duracion = time.perf_counter() - inicio

    assert detectado == tipo
    assert duracion < LIMITE_SEGUNDOS


@pytest.mark.parametrize(
    "contenido",
    [
        pytest.param(_riff_avi(), id="riff-avi"),
        pytest.param(_riff_wav(), id="riff-wav"),
    ],
)
def test_tkt059_ca06_un_riff_que_no_es_webp_no_entra_en_la_lista_blanca(contenido: bytes) -> None:
    """TC-25b · CA-6 · RNF-06 — un RIFF sin `WEBP` en los bytes 8 a 11 no sale como tipo admitido.

    Es la aserción robusta del caso de TC-25b: no fija el tipo exacto que el detector devuelve para
    un AVI o un WAV (`application/octet-stream` hoy), solo que no es `image/webp` ni ningún otro de
    `tipos_admitidos()`. Una lista blanca de fallo abierto dejaría subir como imagen lo que no lo es.
    """
    from cimenta.archivos.dominio.tipos import tipos_admitidos
    from cimenta.archivos.infraestructura.detector_tipo import detectar_tipo

    detectado, _ = _detectar(detectar_tipo, contenido)

    assert detectado != "image/webp"
    assert detectado not in tipos_admitidos()


# ---------------------------------------------------------------------------------------------
# TC-52 · lecturas acotadas: el objeto nunca se lee entero
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("construir", "tipo"),
    [
        pytest.param(_libro_26_mb, TIPO_XLSX, id="libro-26-mb"),
        pytest.param(_directorio_declarado_2_mib, "application/zip", id="directorio-2-mib"),
        pytest.param(_parte_de_2_mib, "application/zip", id="parte-2-mib"),
        pytest.param(_zip64, "application/zip", id="zip64"),
    ],
)
def test_tkt059_ca04_el_detector_lee_rangos_acotados(
    construir: Callable[[], bytes], tipo: str
) -> None:
    """TC-52 · CA-4 · PA-T59.14 — el libro de 26 MB se reconoce leyendo ≤ 262144 bytes; un
    directorio o una parte de 2 MiB, o un ZIP64, se rechazan sin leerlos. Ningún rango pedido
    sale del objeto ni es negativo."""
    from cimenta.archivos.infraestructura.detector_tipo import detectar_tipo

    contenido = construir()
    detectado, lector = _detectar(detectar_tipo, contenido)

    assert detectado == tipo
    assert lector.bytes_leidos <= COTA_LECTURA, (
        f"se leyeron {lector.bytes_leidos} bytes de {lector.tamano}; cota {COTA_LECTURA}"
    )


def test_tkt059_ca04_parte_deflate_que_expande_mas_del_maximo() -> None:
    """TC-52 · CA-4 · PA-T59.14 — una parte DEFLATE de 64 MiB descomprimidos y menos de 1 MiB
    comprimidos se rechaza como ZIP genérico sin descomprimirla entera.

    El resultado no distingue un detector que descomprime con tope de uno que descomprime todo y
    descarta después: ambos dan `application/zip`. Lo que los separa es el pico de memoria, así que
    se mide con `tracemalloc` (los búferes de `zlib` son objetos `bytes` y los registra). Con tope
    de `MAXIMO_PARTE + 1` el pico es de pocos MiB; sin él, de al menos 64 MiB.
    """
    from cimenta.archivos.infraestructura.detector_tipo import detectar_tipo

    contenido = _parte_deflate_que_expande_64_mib()
    assert len(contenido) < MIB, (
        f"el ZIP de la bomba pesa {len(contenido)} bytes; debe pesar < 1 MiB"
    )

    tracemalloc.start()
    try:
        inicio = time.perf_counter()
        detectado, lector = _detectar(detectar_tipo, contenido)
        duracion = time.perf_counter() - inicio
        _, pico = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert detectado == "application/zip"
    assert lector.bytes_leidos <= COTA_LECTURA, (
        f"se leyeron {lector.bytes_leidos} bytes de {lector.tamano}; cota {COTA_LECTURA}"
    )
    assert duracion < LIMITE_SEGUNDOS
    assert pico < PICO_MEMORIA, (
        f"el detector sostuvo {pico} bytes en memoria; tope {PICO_MEMORIA} (¿descomprimió sin tope?)"
    )


# ---------------------------------------------------------------------------------------------
# Revisión ciclo 1 · rojos: el límite de la parte y el ZIP con dos `[Content_Types].xml`
# ---------------------------------------------------------------------------------------------

MAXIMO_PARTE = 262_144  # 256 KiB: el tope de `[Content_Types].xml` que fija Seguridad F002
PARTE_HOJA = "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"

COMPRESIONES = [
    pytest.param(zipfile.ZIP_STORED, id="stored"),
    pytest.param(zipfile.ZIP_DEFLATED, id="deflate"),
]


def _content_types_de_tamano(total: int) -> bytes:
    """`[Content_Types].xml` válido, con la parte de libro de `.xlsx` declarada primero, de
    exactamente `total` bytes. El relleno son etiquetas hermanas `<a/>` (sin anidar, para no
    depender de la profundidad de recursión del analizador) y, si falta, blancos."""
    cabeza = _content_types(("/xl/workbook.xml", PARTE_XLSX)).removesuffix(b"</Types>")
    hueco = total - len(cabeza) - len(b"</Types>")
    assert hueco >= 0
    return cabeza + b"<a/>" * (hueco // 4) + b" " * (hueco % 4) + b"</Types>"


def _libro_con_content_types(content_types: bytes, compresion: int) -> bytes:
    return _zip(
        {"[Content_Types].xml": content_types, "xl/workbook.xml": b"<workbook/>"},
        compresion=compresion,
    )


@pytest.fixture
def partes_analizadas(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Anota el tamaño de cada documento que el detector entrega al analizador de `defusedxml`
    (`fromstring`), y delega en el real. Una parte que no se analiza no deja rastro aquí."""
    original = defusedxml.ElementTree.fromstring
    analizadas: list[int] = []

    def _espia(texto: Any, *args: Any, **kwargs: Any) -> Any:
        analizadas.append(len(texto))
        return original(texto, *args, **kwargs)

    monkeypatch.setattr(defusedxml.ElementTree, "fromstring", _espia)
    return analizadas


@pytest.mark.parametrize("compresion", COMPRESIONES)
def test_tkt059_ca04_parte_de_300_kib_es_zip_generico(
    compresion: int, partes_analizadas: list[int]
) -> None:
    """TC-52 · CA-4 · Seguridad F002 — un `[Content_Types].xml` válido de 300 KiB que declara la
    parte de libro sale como `application/zip` y ni siquiera se analiza.

    Con `MAXIMO_PARTE` en 256 KiB, una parte STORED de 300 KiB se descarta por su tamaño
    comprimido, sin leerla; una DEFLATE de 300 KiB descomprimidos, al pasar el tope de la
    descompresión. En ningún caso llega al analizador de XML ni la lectura pasa de la cota.
    """
    from cimenta.archivos.infraestructura.detector_tipo import detectar_tipo

    contenido = _libro_con_content_types(_content_types_de_tamano(300 * 1024), compresion)
    detectado, lector = _detectar(detectar_tipo, contenido)

    assert detectado == "application/zip"
    assert lector.bytes_leidos <= COTA_LECTURA, (
        f"se leyeron {lector.bytes_leidos} bytes de {lector.tamano}; cota {COTA_LECTURA}"
    )
    assert partes_analizadas == [], "el detector analizó una parte que excede MAXIMO_PARTE"


@pytest.mark.parametrize("compresion", COMPRESIONES)
def test_tkt059_ca04_parte_real_de_10_kib_sigue_siendo_xlsx(compresion: int) -> None:
    """TC-52 · CA-4 · Seguridad F002 — bajar el tope no estorba a un libro real: un
    `[Content_Types].xml` de unos 10 KiB (hojas declaradas) sigue dando `.xlsx` y se lee dentro de
    la cota."""
    from cimenta.archivos.infraestructura.detector_tipo import detectar_tipo

    sobrescrituras = [("/xl/workbook.xml", PARTE_XLSX)] + [
        (f"/xl/worksheets/sheet{n}.xml", PARTE_HOJA) for n in range(1, 71)
    ]
    content_types = _content_types(*sobrescrituras)
    assert 9_000 <= len(content_types) <= 12_000, len(content_types)

    contenido = _libro_con_content_types(content_types, compresion)
    detectado, lector = _detectar(detectar_tipo, contenido)

    assert detectado == TIPO_XLSX
    assert lector.bytes_leidos <= COTA_LECTURA


@pytest.mark.parametrize("compresion", COMPRESIONES)
@pytest.mark.parametrize(
    ("tamano_parte", "tipo"),
    [
        pytest.param(MAXIMO_PARTE, TIPO_XLSX, id="exactamente-el-maximo"),
        pytest.param(MAXIMO_PARTE + 1, "application/zip", id="un-byte-sobre-el-maximo"),
    ],
)
def test_tkt059_ca04_el_limite_de_la_parte_es_inclusivo(
    compresion: int, tamano_parte: int, tipo: str
) -> None:
    """TC-52 · CA-4 · Seguridad F002 — `[Content_Types].xml` de exactamente 256 KiB se acepta
    (sea STORED, por su tamaño comprimido, o DEFLATE, por el descomprimido) y uno de 256 KiB más un
    byte se rechaza: el límite es inclusivo."""
    from cimenta.archivos.infraestructura.detector_tipo import detectar_tipo

    contenido = _libro_con_content_types(_content_types_de_tamano(tamano_parte), compresion)
    detectado, _ = _detectar(detectar_tipo, contenido)

    assert detectado == tipo


def _zip_con_dos_content_types() -> bytes:
    """Dos entradas `[Content_Types].xml`: la primera declara la parte de libro; la última es
    `<Types/>`. `zipfile` admite el duplicado con un aviso, que aquí se silencia."""
    buf = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("[Content_Types].xml", _content_types(("/xl/workbook.xml", PARTE_XLSX)))
            zf.writestr("xl/workbook.xml", b"<workbook/>")
            zf.writestr("[Content_Types].xml", b"<Types/>")
    return buf.getvalue()


def test_tkt059_ca06_zip_con_dos_content_types_no_es_xlsx() -> None:
    """TC-25b · CA-6 · Seguridad O1 — con dos entradas `[Content_Types].xml`, `zipfile` (y con él
    `openpyxl`) lee la última, que no declara nada: el detector no puede dar `.xlsx` por la primera.
    """
    from cimenta.archivos.infraestructura.detector_tipo import detectar_tipo

    contenido = _zip_con_dos_content_types()
    with zipfile.ZipFile(io.BytesIO(contenido)) as zf:
        assert zf.read("[Content_Types].xml") == b"<Types/>"  # lo que leería el consumidor

    detectado, _ = _detectar(detectar_tipo, contenido)

    assert detectado == "application/zip"


def _zip_con_dos_content_types_en_orden_inverso() -> bytes:
    """Dos entradas `[Content_Types].xml`: la primera es `<Types/>`; la última declara la parte de
    libro. `zipfile` lee la última, así que el consumidor vería un `.xlsx`."""
    buf = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("[Content_Types].xml", b"<Types/>")
            zf.writestr("xl/workbook.xml", b"<workbook/>")
            zf.writestr("[Content_Types].xml", _content_types(("/xl/workbook.xml", PARTE_XLSX)))
    return buf.getvalue()


def test_tkt059_ca06_zip_con_dos_content_types_en_orden_inverso_no_es_xlsx() -> None:
    """TC-25b · CA-6 · Código F006 — con la parte de libro en la última entrada duplicada, el
    detector tampoco da `.xlsx`: el duplicado se rechaza se vea primero o último.

    Mata el mutante que reemplaza `if encontrada is not None:` por `if False:`: sin el rechazo, la
    última entrada pisa a la primera y este ZIP saldría como `.xlsx` (el test de orden directo no
    lo distingue, porque la última de aquel es `<Types/>`).
    """
    from cimenta.archivos.infraestructura.detector_tipo import detectar_tipo

    contenido = _zip_con_dos_content_types_en_orden_inverso()
    with zipfile.ZipFile(io.BytesIO(contenido)) as zf:  # la premisa: lo que leería el consumidor
        assert b"Override" in zf.read("[Content_Types].xml")

    detectado, _ = _detectar(detectar_tipo, contenido)

    assert detectado == "application/zip"


# ---------------------------------------------------------------------------------------------
# Revisión ciclo 2 · la candidata de máxima confianza decide el respaldo (Código F005, Seguridad O4)
# ---------------------------------------------------------------------------------------------


def _pdf_con_firma_tar() -> bytes:
    """Cabecera de PDF con `ustar` en los bytes 257 a 261.

    Premisa, comprobada con `puremagic` real: la firma `.tar` (`application/x-tar`) tiene
    confianza 0,5 y la de `%PDF` (`.pdf`, `application/pdf`) 0,4. La de máxima confianza no está en
    `EXTENSIONES` y sí tiene `mime_type`; `.pdf` sí está, pero con menor confianza.
    """
    cabecera = bytearray(b"%PDF-1.7\n" + b"\x00" * 600)
    cabecera[257:262] = b"ustar"
    return bytes(cabecera)


def _jpeg_con_firma_mod() -> bytes:
    """Cabecera JFIF con `10CH` en los bytes 1080 a 1083.

    Premisa, comprobada con `puremagic` real: la firma `.mod` (módulo de Fast Tracker, `mime_type`
    vacío) tiene confianza 0,4 y las de JPEG (`image/jpeg`) 0,3 y 0,2. La de máxima confianza no
    está en `EXTENSIONES` y no tiene tipo; las de `image/jpeg` son más débiles.
    """
    cabecera = bytearray(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"\x00" * 2048)
    cabecera[1080:1084] = b"10CH"
    return bytes(cabecera)


def test_tkt059_ca06_una_candidata_de_mayor_confianza_fuera_de_la_lista_blanca_gana() -> None:
    """TC-25b · CA-6 · RNF-06 · Código F005 — un PDF con la firma de `.tar` (0,5 contra 0,4 del PDF)
    sale como `application/x-tar`, no como `application/pdf`.

    Mata el mutante que borra `candidata.confidence == maxima and` en `_tipo_por_firma`: sin el
    filtro, la candidata `.pdf`, más débil, entraría por la lista blanca.
    """
    from cimenta.archivos.infraestructura.detector_tipo import detectar_tipo

    detectado, _ = _detectar(detectar_tipo, _pdf_con_firma_tar())

    assert detectado == "application/x-tar"


def test_tkt059_ca06_una_candidata_debil_con_tipo_admitido_no_abre_la_lista_blanca() -> None:
    """TC-25b · CA-6 · RNF-06 · Código F005 — un JPEG con la firma de `.mod` (0,4, sin tipo) no sale
    como `image/jpeg`: la candidata de máxima confianza no es de la lista blanca, y el respaldo no
    puede devolver el `mime_type` de una candidata más débil que sí lo es.

    La aserción es la robusta: no fija el tipo exacto que devolverá la corrección (lo esperable es
    `application/octet-stream`), solo que no es ninguno de `tipos_admitidos()`. Hoy sale
    `image/jpeg` y la prueba falla por esa razón.
    """
    from cimenta.archivos.dominio.tipos import tipos_admitidos
    from cimenta.archivos.infraestructura.detector_tipo import detectar_tipo

    detectado, _ = _detectar(detectar_tipo, _jpeg_con_firma_mod())

    assert detectado != "image/jpeg"
    assert detectado not in tipos_admitidos()


def test_tkt059_ca06_jpeg_con_solo_dos_bytes_de_firma_sigue_siendo_jpeg() -> None:
    """TC-25 · CA-6 · RNF-06 · Seguridad O4 — `\\xff\\xd8` sin tercer byte tiene una única candidata
    (`.jpe`, `image/jpeg`, confianza 0,2): es de máxima confianza, así que su tipo se conserva.

    Verde a propósito: protege el caso de candidata única de una corrección del respaldo que solo
    aceptara tipos de la lista blanca por `EXTENSIONES`. `.jpe` no está en `EXTENSIONES`; llega por
    el respaldo.
    """
    from cimenta.archivos.infraestructura.detector_tipo import detectar_tipo

    detectado, _ = _detectar(detectar_tipo, b"\xff\xd8" + b"\x00" * 64)

    assert detectado == "image/jpeg"


# ---------------------------------------------------------------------------------------------
# Revisión ciclo 1 · verdes de cobertura: ramas defensivas del detector
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("contenido", "tipo"),
    [
        pytest.param(b"", "application/octet-stream", id="vacio"),
        pytest.param(b"P", "application/octet-stream", id="un-byte"),
        pytest.param(b"PK", "application/octet-stream", id="dos-bytes"),
        pytest.param(b"PK\x03", "application/octet-stream", id="tres-bytes"),
        pytest.param(b"PK\x03\x04", "application/zip", id="solo-la-firma-zip"),
        pytest.param(
            b"PK\x03\x04PK\x05\x06" + b"\x00" * 10, "application/zip", id="registro-de-fin-truncado"
        ),
    ],
)
def test_tkt059_ca04_objeto_diminuto_no_pide_rangos_fuera_del_objeto(
    contenido: bytes, tipo: str
) -> None:
    """TC-52 · CA-4 — un objeto de 0 a 3 bytes, o con una firma ZIP sin directorio, se clasifica
    sin pedir un rango negativo ni más allá de `tamano` (`_detectar` lo exige)."""
    from cimenta.archivos.infraestructura.detector_tipo import detectar_tipo

    detectado, lector = _detectar(detectar_tipo, contenido)

    assert detectado == tipo
    assert lector.fuera_de_rango == []


def _xlsx_con_comentario_de_65535() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _content_types(("/xl/workbook.xml", PARTE_XLSX)))
        zf.writestr("xl/workbook.xml", b"<workbook/>")
        zf.comment = b"c" * 65535
    return buf.getvalue()


def _xlsx_con_comentario_y_un_byte_de_mas() -> bytes:
    """El comentario máximo de ZIP más un byte: el registro de fin queda a 65558 bytes del final,
    fuera de la cola que lee el detector (y fuera de la que busca `zipfile`)."""
    return _xlsx_con_comentario_de_65535() + b"c"


@pytest.mark.parametrize(
    ("construir", "tipo"),
    [
        pytest.param(_xlsx_con_comentario_de_65535, TIPO_XLSX, id="comentario-de-65535"),
        pytest.param(
            _xlsx_con_comentario_y_un_byte_de_mas, "application/zip", id="comentario-de-65536"
        ),
    ],
)
def test_tkt059_ca04_la_cola_del_zip_cubre_el_comentario_maximo(
    construir: Callable[[], bytes], tipo: str
) -> None:
    """TC-52 · CA-4 — el `.xlsx` con el comentario máximo de ZIP (65535 bytes) se reconoce; con un
    byte más tras el registro de fin, el detector no lo encuentra en su cola de 65557 bytes y lo
    degrada a ZIP genérico, sin pedir rangos fuera del objeto."""
    from cimenta.archivos.infraestructura.detector_tipo import detectar_tipo

    contenido = construir()
    detectado, _ = _detectar(detectar_tipo, contenido)

    assert detectado == tipo


@pytest.mark.parametrize(
    "recorte",
    [
        pytest.param(slice(None, -10), id="sin-los-ultimos-10"),
        pytest.param(slice(100), id="100-bytes"),
    ],
)
def test_tkt059_ca06_zip_truncado_es_zip_generico(recorte: slice) -> None:
    """TC-25b · CA-6 — un `.xlsx` cortado (sin parte del registro de fin, o solo con sus primeros
    100 bytes) sale como `application/zip` sin excepción ni rangos fuera del objeto."""
    from cimenta.archivos.infraestructura.detector_tipo import detectar_tipo

    contenido = _xlsx_valido_minimo()[recorte]
    detectado, _ = _detectar(detectar_tipo, contenido)

    assert detectado == "application/zip"


def _datos_comprimidos(contenido: bytes, nombre: str) -> tuple[int, int]:
    """Posición `[inicio, fin)` de los datos comprimidos de una entrada, según su cabecera local."""
    with zipfile.ZipFile(io.BytesIO(contenido)) as zf:
        info = zf.getinfo(nombre)
    nlen, elen = struct.unpack_from("<HH", contenido, info.header_offset + 26)
    inicio = info.header_offset + 30 + nlen + elen
    return inicio, inicio + info.compress_size


def test_tkt059_ca06_deflate_corrupto_es_zip_generico() -> None:
    """TC-25b · CA-6 — un `[Content_Types].xml` DEFLATE con los bytes comprimidos invertidos hace
    fallar a `zlib`; el detector lo traduce a `application/zip` y no deja pasar la excepción."""
    from cimenta.archivos.infraestructura.detector_tipo import detectar_tipo

    base = _xlsx_valido_minimo()
    inicio, fin = _datos_comprimidos(base, "[Content_Types].xml")
    invertidos = bytes(octeto ^ 0xFF for octeto in base[inicio:fin])
    with pytest.raises(zlib.error):  # la premisa: esta corrupción sí hace fallar a zlib
        zlib.decompressobj(-15).decompress(invertidos)
    contenido = base[:inicio] + invertidos + base[fin:]

    detectado, _ = _detectar(detectar_tipo, contenido)

    assert detectado == "application/zip"


def test_tkt059_ca06_content_types_stored_es_xlsx() -> None:
    """TC-25b · CA-6 — un `[Content_Types].xml` sin comprimir (método 0) se lee tal cual."""
    from cimenta.archivos.infraestructura.detector_tipo import detectar_tipo

    contenido = _libro_con_content_types(
        _content_types(("/xl/workbook.xml", PARTE_XLSX)), zipfile.ZIP_STORED
    )
    detectado, _ = _detectar(detectar_tipo, contenido)

    assert detectado == TIPO_XLSX


def test_tkt059_ca06_entrada_con_nombre_unicode_antes_de_content_types() -> None:
    """TC-25b · CA-6 — el recorrido del directorio avanza por bytes, no por caracteres: una entrada
    previa llamada `ñandú/日本.xml` no desalinea la búsqueda de `[Content_Types].xml`."""
    from cimenta.archivos.infraestructura.detector_tipo import detectar_tipo

    contenido = _zip(
        {
            "ñandú/日本.xml": b"<x/>",
            "[Content_Types].xml": _content_types(("/xl/workbook.xml", PARTE_XLSX)),
            "xl/workbook.xml": b"<workbook/>",
        }
    )
    detectado, _ = _detectar(detectar_tipo, contenido)

    assert detectado == TIPO_XLSX


def test_tkt059_ca06_entradas_con_extra_y_comentario_no_desalinean_el_recorrido() -> None:
    """TC-25b · CA-6 — la longitud del extra y la del comentario de cada entrada del directorio, y
    la del extra de la cabecera local, se suman al avanzar: un libro cuyas entradas las traen
    sigue siendo `.xlsx`."""
    from cimenta.archivos.infraestructura.detector_tipo import detectar_tipo

    def _entrada(nombre: str) -> zipfile.ZipInfo:
        info = zipfile.ZipInfo(nombre)
        info.compress_type = zipfile.ZIP_DEFLATED
        info.extra = b"\x99\x99\x04\x00abcd"
        info.comment = b"comentario de la entrada"
        return info

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(_entrada("docProps/app.xml"), b"<Properties/>")
        zf.writestr(
            _entrada("[Content_Types].xml"), _content_types(("/xl/workbook.xml", PARTE_XLSX))
        )
        zf.writestr(_entrada("xl/workbook.xml"), b"<workbook/>")
    contenido = buf.getvalue()
    with zipfile.ZipFile(io.BytesIO(contenido)) as zf:  # la premisa: extra y comentario existen
        assert zf.getinfo("docProps/app.xml").extra == b"\x99\x99\x04\x00abcd"
        assert zf.getinfo("docProps/app.xml").comment == b"comentario de la entrada"

    detectado, _ = _detectar(detectar_tipo, contenido)

    assert detectado == TIPO_XLSX


# --- Parches a bajo nivel sobre un libro con una entrada previa a `[Content_Types].xml` -----------

_CENTRAL_METODO = 10
_CENTRAL_COMPRIMIDO = 20
_CENTRAL_DESPLAZAMIENTO = 42
_LOCAL_LONGITUD_EXTRA = 28


def _libro_con_entrada_previa() -> bytes:
    """`.xlsx` válido cuya primera entrada no es `[Content_Types].xml`, para poder estropear la
    cabecera local de esta sin que el detector deje de ver la firma `PK\\x03\\x04` al principio."""
    return _zip(
        {
            "docProps/app.xml": b"<Properties/>",
            "[Content_Types].xml": _content_types(("/xl/workbook.xml", PARTE_XLSX)),
            "xl/workbook.xml": b"<workbook/>",
        }
    )


def _inicio_directorio(contenido: bytes) -> int:
    return int(struct.unpack("<4sHHHHIIH", contenido[-22:])[6])


def _posicion_central(contenido: bytes, nombre: bytes) -> int:
    posicion = _inicio_directorio(contenido)
    while contenido[posicion : posicion + 4] == b"PK\x01\x02":
        nlen, elen, clen = struct.unpack_from("<HHH", contenido, posicion + 28)
        if contenido[posicion + 46 : posicion + 46 + nlen] == nombre:
            return posicion
        posicion += 46 + nlen + elen + clen
    raise AssertionError(f"el directorio no tiene {nombre!r}")


def _escribir(contenido: bytes, posicion: int, formato: str, *valores: Any) -> bytes:
    nuevo = struct.pack(formato, *valores)
    return contenido[:posicion] + nuevo + contenido[posicion + len(nuevo) :]


def _con_campo_central(contenido: bytes, desplazamiento: int, formato: str, *valores: Any) -> bytes:
    posicion = _posicion_central(contenido, b"[Content_Types].xml") + desplazamiento
    return _escribir(contenido, posicion, formato, *valores)


def _con_campo_local(contenido: bytes, desplazamiento: int, formato: str, *valores: Any) -> bytes:
    with zipfile.ZipFile(io.BytesIO(contenido)) as zf:
        inicio = zf.getinfo("[Content_Types].xml").header_offset
    return _escribir(contenido, inicio + desplazamiento, formato, *valores)


def _con_metodo(metodo: int) -> bytes:
    """El libro de deflate con el método de `[Content_Types].xml` cambiado en el directorio. Los
    datos siguen siendo deflate válido: un detector que aceptara cualquier método los leería."""
    return _con_campo_central(_libro_con_entrada_previa(), _CENTRAL_METODO, "<H", metodo)


def _libro_con_metodo_real(metodo: int) -> bytes:
    return _zip(
        {
            "[Content_Types].xml": _content_types(("/xl/workbook.xml", PARTE_XLSX)),
            "xl/workbook.xml": b"<workbook/>",
        },
        compresion=metodo,
    )


@pytest.mark.parametrize(
    "construir",
    [
        pytest.param(lambda: _con_metodo(9), id="metodo-9-deflate64"),
        pytest.param(lambda: _con_metodo(12), id="metodo-12-bzip2-declarado"),
        pytest.param(lambda: _con_metodo(14), id="metodo-14-lzma-declarado"),
        pytest.param(lambda: _con_metodo(99), id="metodo-99-aes"),
        pytest.param(lambda: _libro_con_metodo_real(zipfile.ZIP_BZIP2), id="bzip2-real"),
        pytest.param(lambda: _libro_con_metodo_real(zipfile.ZIP_LZMA), id="lzma-real"),
    ],
)
def test_tkt059_ca06_metodo_de_compresion_distinto_de_stored_y_deflate_es_zip_generico(
    construir: Callable[[], bytes],
) -> None:
    """TC-25b · CA-6 — solo se leen los métodos 0 (STORED) y 8 (DEFLATE). Con otro método
    declarado, aunque los datos fueran deflate válido, el detector no los interpreta y da
    `application/zip`."""
    from cimenta.archivos.infraestructura.detector_tipo import detectar_tipo

    detectado, _ = _detectar(detectar_tipo, construir())

    assert detectado == "application/zip"


def _con_firma_local_corrupta() -> bytes:
    return _con_campo_local(_libro_con_entrada_previa(), 0, "<4s", b"PK\x03\x05")


def _con_extra_local_enorme() -> bytes:
    """Los datos empezarían 65535 bytes después de la cabecera local, más allá del directorio."""
    return _con_campo_local(_libro_con_entrada_previa(), _LOCAL_LONGITUD_EXTRA, "<H", 0xFFFF)


def _con_comprimido_mayor_que_el_objeto() -> bytes:
    """El directorio declara 200 000 bytes comprimidos (dentro del tope de parte) en un objeto de
    menos de un KiB."""
    return _con_campo_central(_libro_con_entrada_previa(), _CENTRAL_COMPRIMIDO, "<I", 200_000)


def _con_comprimido_cero() -> bytes:
    return _con_campo_central(_libro_con_entrada_previa(), _CENTRAL_COMPRIMIDO, "<I", 0)


def _con_cabecera_local_mas_alla_del_final() -> bytes:
    """El desplazamiento de la cabecera local deja menos de 30 bytes hasta el final del objeto: leerla
    pediría un rango que sale de `tamano`."""
    base = _libro_con_entrada_previa()
    return _con_campo_central(base, _CENTRAL_DESPLAZAMIENTO, "<I", len(base) - 10)


@pytest.mark.parametrize(
    "construir",
    [
        pytest.param(_con_firma_local_corrupta, id="firma-local-corrupta"),
        pytest.param(_con_extra_local_enorme, id="extra-local-enorme"),
        pytest.param(_con_comprimido_mayor_que_el_objeto, id="comprimido-mayor-que-el-objeto"),
        pytest.param(_con_comprimido_cero, id="comprimido-cero"),
        pytest.param(
            _con_cabecera_local_mas_alla_del_final, id="cabecera-local-mas-alla-del-final"
        ),
    ],
)
def test_tkt059_ca04_cabecera_local_incoherente_con_el_directorio_es_zip_generico(
    construir: Callable[[], bytes],
) -> None:
    """TC-52 · CA-4 — una cabecera local cuyos datos caerían fuera del espacio anterior al
    directorio central, con firma mala o con tamaño nulo, se rechaza sin leer más allá del objeto:
    `application/zip`, y `_detectar` comprueba que ningún rango salió de `tamano`."""
    from cimenta.archivos.infraestructura.detector_tipo import detectar_tipo

    contenido = construir()
    assert contenido != _libro_con_entrada_previa()  # el parche cambió algo
    detectado, _ = _detectar(detectar_tipo, contenido)

    assert detectado == "application/zip"


def _con_directorio_que_invade_el_registro_de_fin() -> bytes:
    """El registro de fin declara un directorio 10 bytes mayor que el espacio que tiene antes de sí
    mismo: terminaría dentro del propio registro."""
    base = _libro_con_entrada_previa()
    _, _, _, _, _, tamano_directorio, _, _ = struct.unpack("<4sHHHHIIH", base[-22:])
    return _escribir(base, len(base) - 22 + 12, "<I", tamano_directorio + 10)


def _con_firma_central_corrupta() -> bytes:
    """La primera entrada del directorio central no empieza por la firma de entrada
    (`PK` seguida de 0x01 y 0x02): el directorio no es de fiar y el detector no sigue
    recorriéndolo."""
    base = _libro_con_entrada_previa()
    return _escribir(base, _inicio_directorio(base), "<4s", b"PK\x01\x03")


@pytest.mark.parametrize(
    "construir",
    [
        pytest.param(
            _con_directorio_que_invade_el_registro_de_fin, id="directorio-que-invade-el-registro"
        ),
        pytest.param(_con_firma_central_corrupta, id="firma-central-corrupta"),
    ],
)
def test_tkt059_ca06_directorio_incoherente_es_zip_generico(
    construir: Callable[[], bytes],
) -> None:
    """TC-25b · CA-6 — un directorio central que invade el registro de fin, o cuya primera entrada
    no lleva la firma de entrada, no se interpreta aunque más adelante tuviera un
    `[Content_Types].xml` válido: `application/zip`."""
    from cimenta.archivos.infraestructura.detector_tipo import detectar_tipo

    contenido = construir()
    assert contenido != _libro_con_entrada_previa()  # el parche cambió algo
    detectado, _ = _detectar(detectar_tipo, contenido)

    assert detectado == "application/zip"


def test_tkt059_ca04_un_almacen_que_devuelve_vacio_no_rompe_el_detector() -> None:
    """TC-52 · CA-4 — si `leer_rango` devuelve una cabecera vacía aunque `tamano` sea mayor que
    cero (un almacén que falla en silencio), `puremagic` rechaza la entrada vacía y el detector
    responde `application/octet-stream` en lugar de dejar pasar la excepción."""
    from cimenta.archivos.infraestructura.detector_tipo import detectar_tipo

    assert detectar_tipo(lambda inicio, fin: b"", 10) == "application/octet-stream"
