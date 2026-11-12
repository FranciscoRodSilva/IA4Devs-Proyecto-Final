"""Detector del tipo MIME por los bytes del objeto (TKT-059, fila 6).

Implementa RNF-06 y PA-T59.14 sobre el almacén de objetos de ADR-016: el tipo sale del contenido y
nunca de la extensión del nombre ni de lo que declare el cliente, y el objeto nunca se descarga
entero. Todo se lee con `leer_rango(inicio, fin)`, con los dos extremos inclusivos y dentro de
`tamano`. El orden de decisión es el de la fila 6 del diseño: cabecera de 8 KiB; ZIP, que lee solo
el directorio y la parte `[Content_Types].xml`, con límites de tamaño y sin expandir nada; XML, con
DTD, entidades y referencias externas prohibidas; firmas propias de HEIC y MP4; y, por último,
`puremagic`. Lo que no esté en la lista blanca sale con su tipo exacto, para que el caso de uso lo
rechace con el dato que necesita. Sin efectos secundarios fuera de las lecturas de `leer_rango`.
"""

import struct
import zlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

import puremagic
from defusedxml import ElementTree as defused_et
from defusedxml.common import DTDForbidden, EntitiesForbidden, ExternalReferenceForbidden
from puremagic.main import PureError, PureValueError

from cimenta.archivos.dominio.tipos import TIPO_XLSX, tipos_admitidos

CABECERA: Final = 8192
COLA_ZIP: Final = 65557
MAXIMO_DIRECTORIO: Final = 1_048_576
# Un `[Content_Types].xml` real pesa pocas decenas de KiB. El tope es de 256 KiB, comprimida y
# descomprimida, por la bomba de profundidad XML (RNF-06): 1 MiB de etiquetas anidadas llegó a
# 97 MiB de pico de memoria al analizarlo. El límite es inclusivo: 262144 bytes se analizan.
MAXIMO_PARTE: Final = 262_144

TIPO_ZIP: Final = "application/zip"
TIPO_OCTETO: Final = "application/octet-stream"
TIPO_TEXTO: Final = "text/plain"
TIPO_XML: Final = "application/xml"
TIPO_XML_DTD: Final = "application/xml-dtd"
TIPO_SVG: Final = "image/svg+xml"
TIPO_HEIC: Final = "image/heic"
TIPO_MP4: Final = "video/mp4"
TIPO_WEBP: Final = "image/webp"
PARTE_XLSX: Final = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"

EXTENSIONES: Final[dict[str, str]] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": TIPO_WEBP,
    ".heic": TIPO_HEIC,
    ".heif": TIPO_HEIC,
    ".mp4": TIPO_MP4,
    ".pdf": "application/pdf",
}

LeerRango = Callable[[int, int], bytes]

_FIRMA_LOCAL: Final = b"PK\x03\x04"
_FIRMA_CENTRAL: Final = b"PK\x01\x02"
_FIRMA_FIN: Final = b"PK\x05\x06"
_NOMBRE_CONTENT_TYPES: Final = b"[Content_Types].xml"
_MARCA_16: Final = 0xFFFF
_MARCA_32: Final = 0xFFFFFFFF
_EOCD: Final = struct.Struct("<4sHHHHIIH")
_CENTRAL: Final = struct.Struct("<4sHHHHHHIIIHHHHHII")
_LOCAL: Final = struct.Struct("<4sHHHHHIIIHH")
_UTF8_BOM: Final = b"\xef\xbb\xbf"
_BLANCOS: Final = b" \t\r\n"
_MARCAS_HEIC: Final = frozenset({b"heic", b"heix", b"mif1", b"msf1"})


@dataclass(frozen=True)
class _EntradaCentral:
    metodo: int
    comprimido: int
    desplazamiento: int


class _PrimeraEtiqueta:
    """Destino del analizador que guarda el nombre de la primera etiqueta y se olvida del resto."""

    def __init__(self) -> None:
        self.nombre: str | None = None

    def start(self, tag: str, attrib: dict[str, str]) -> None:
        if self.nombre is None:
            self.nombre = tag


def detectar_tipo(leer_rango: LeerRango, tamano: int) -> str:
    """Implementa RNF-06 y PA-T59.14 · devuelve el tipo MIME que dicen los bytes del objeto.

    `leer_rango(inicio, fin)` devuelve los bytes `inicio..fin`, ambos inclusivos, y nunca se pide
    un rango negativo ni fuera de `tamano`. El resultado es un tipo de la lista blanca cuando el
    contenido lo es, y un tipo exacto en cualquier otro caso (`application/zip` para un `.xlsm`,
    `image/svg+xml` para un SVG, `application/octet-stream` para lo que no reconoce). Decidir si el
    tipo se admite corresponde al caso de uso, no a este detector.
    """
    if tamano <= 0:
        return TIPO_OCTETO
    cabecera = leer_rango(0, min(tamano, CABECERA) - 1)
    if cabecera.startswith(_FIRMA_LOCAL):
        return _tipo_zip(leer_rango, tamano)
    cuerpo = _sin_bom_ni_blancos(cabecera)
    if cuerpo.startswith(b"<"):
        return _tipo_xml(cuerpo)
    return _tipo_por_firma(cabecera)


def _sin_bom_ni_blancos(cabecera: bytes) -> bytes:
    """Quita el BOM UTF-8 y los blancos iniciales, para ver si el documento empieza por `<`.

    `puremagic` no reconoce el XML con BOM ni con blancos al principio, así que el paso XML debe
    verlo sin ellos (PA-T59.14).
    """
    return cabecera.removeprefix(_UTF8_BOM).lstrip(_BLANCOS)


def _tipo_zip(leer_rango: LeerRango, tamano: int) -> str:
    """Implementa RNF-06 · distingue un `.xlsx` de cualquier otro ZIP leyendo solo lo necesario.

    Un ZIP cuyo `[Content_Types].xml` no declara la parte de libro de `.xlsx` sale como
    `application/zip`, lo que incluye al `.xlsm` con macros. Un ZIP64, un directorio mayor que
    `MAXIMO_DIRECTORIO` o una parte mayor que `MAXIMO_PARTE` se rechazan sin leerlos.
    """
    localizado = _leer_directorio(leer_rango, tamano)
    if localizado is None:
        return TIPO_ZIP
    inicio_directorio, directorio = localizado
    entrada = _buscar_content_types(directorio)
    if entrada is None:
        return TIPO_ZIP
    parte = _leer_parte(leer_rango, entrada, inicio_directorio)
    if parte is None:
        return TIPO_ZIP
    return TIPO_XLSX if _declara_libro_xlsx(parte) else TIPO_ZIP


def _leer_directorio(leer_rango: LeerRango, tamano: int) -> tuple[int, bytes] | None:
    """Lee el registro de fin del directorio desde la cola y después el directorio central.

    Devuelve el desplazamiento y los bytes del directorio, o `None` si no hay un directorio que
    quepa en los límites: sin firma de fin, ZIP64, directorio mayor que `MAXIMO_DIRECTORIO` o que
    no termina antes del registro de fin.
    """
    inicio_cola = max(0, tamano - COLA_ZIP)
    cola = leer_rango(inicio_cola, tamano - 1)
    pos = cola.rfind(_FIRMA_FIN)
    if pos < 0 or len(cola) - pos < _EOCD.size:
        return None
    _, _, _, _, entradas, tamano_directorio, inicio_directorio, _ = _EOCD.unpack_from(cola, pos)
    if entradas == _MARCA_16 or tamano_directorio == _MARCA_32 or inicio_directorio == _MARCA_32:
        return None
    fin_registro = inicio_cola + pos
    if not 0 < tamano_directorio <= MAXIMO_DIRECTORIO:
        return None
    if inicio_directorio + tamano_directorio > fin_registro:
        return None
    return inicio_directorio, leer_rango(
        inicio_directorio, inicio_directorio + tamano_directorio - 1
    )


def _buscar_content_types(directorio: bytes) -> _EntradaCentral | None:
    """Recorre el directorio central y devuelve la entrada de `[Content_Types].xml`.

    Si el nombre aparece más de una vez devuelve `None` (RNF-06).
    """
    encontrada: _EntradaCentral | None = None
    posicion = 0
    while posicion + _CENTRAL.size <= len(directorio):
        (
            firma,
            _,
            _,
            _,
            metodo,
            _,
            _,
            _,
            comprimido,
            _,
            nlen,
            elen,
            clen,
            _,
            _,
            _,
            desplazamiento,
        ) = _CENTRAL.unpack_from(directorio, posicion)
        if firma != _FIRMA_CENTRAL:
            return None
        inicio_nombre = posicion + _CENTRAL.size
        if directorio[inicio_nombre : inicio_nombre + nlen] == _NOMBRE_CONTENT_TYPES:
            if encontrada is not None:
                # Dos entradas con el mismo nombre: zipfile y openpyxl toman la última, así que
                # el resultado sería ambiguo y el archivo queda como ZIP genérico.
                return None
            encontrada = _EntradaCentral(metodo, comprimido, desplazamiento)
        posicion = inicio_nombre + nlen + elen + clen
    return encontrada


def _leer_parte(
    leer_rango: LeerRango, entrada: _EntradaCentral, inicio_directorio: int
) -> bytes | None:
    """Lee la parte `[Content_Types].xml` por rangos y la descomprime con un límite.

    Lee la cabecera local (30 bytes) y después los datos comprimidos. La longitud del nombre y del
    extra se toma de la cabecera local y se suma al desplazamiento sin leerlos. Devuelve `None` si
    el método no es `stored` ni `deflate`, si la parte comprimida o descomprimida excede
    `MAXIMO_PARTE`, o si la parte no se puede descomprimir.
    """
    if entrada.metodo not in (0, 8) or not 0 < entrada.comprimido <= MAXIMO_PARTE:
        return None
    if entrada.desplazamiento + _LOCAL.size > inicio_directorio:
        return None
    cabecera_local = leer_rango(entrada.desplazamiento, entrada.desplazamiento + _LOCAL.size - 1)
    campos = _LOCAL.unpack(cabecera_local)
    if campos[0] != _FIRMA_LOCAL:
        return None
    nlen, elen = campos[9], campos[10]
    inicio_datos = entrada.desplazamiento + _LOCAL.size + nlen + elen
    if inicio_datos + entrada.comprimido > inicio_directorio:
        return None
    datos = leer_rango(inicio_datos, inicio_datos + entrada.comprimido - 1)
    if entrada.metodo == 0:
        return datos
    try:
        parte = zlib.decompressobj(-15).decompress(datos, MAXIMO_PARTE + 1)
    except zlib.error:
        return None
    return parte if len(parte) <= MAXIMO_PARTE else None


def _declara_libro_xlsx(parte: bytes) -> bool:
    """Implementa RNF-06 · ¿declara algún `Override` la parte de libro de `.xlsx`?

    Con `forbid_dtd`, un `[Content_Types].xml` con DOCTYPE o entidades no declara nada y sale como
    ZIP genérico.
    """
    try:
        raiz = defused_et.fromstring(parte, forbid_dtd=True)
    except (DTDForbidden, EntitiesForbidden, ExternalReferenceForbidden):
        return False
    except (defused_et.ParseError, LookupError, ValueError):
        # codificación declarada que expat no admite: falla antes de la primera etiqueta
        return False
    return any(
        _nombre_local(elemento.tag) == "Override" and elemento.get("ContentType") == PARTE_XLSX
        for elemento in raiz.iter()
    )


def _tipo_xml(cuerpo: bytes) -> str:
    """Implementa RNF-06 · clasifica un documento que empieza por `<` sin cargar su contenido.

    Solo se alimenta el analizador con la cabecera, sin `close()`: basta la primera etiqueta. Un
    DTD, una entidad o una referencia externa salen como `application/xml-dtd` (P-9). Un texto que
    empieza por `<` pero no es XML sale como `text/plain`, porque falla antes de la primera
    etiqueta.
    """
    destino = _PrimeraEtiqueta()
    analizador = defused_et.DefusedXMLParser(
        target=destino, forbid_dtd=True, forbid_entities=True, forbid_external=True
    )
    try:
        analizador.feed(cuerpo)
    except (DTDForbidden, EntitiesForbidden, ExternalReferenceForbidden):
        return TIPO_XML_DTD
    except (defused_et.ParseError, LookupError, ValueError):
        # codificación declarada que expat no admite: falla antes de la primera etiqueta
        pass
    if destino.nombre is None:
        return TIPO_TEXTO
    if _nombre_local(destino.nombre) == "svg":
        return TIPO_SVG
    return TIPO_XML


def _tipo_por_firma(cabecera: bytes) -> str:
    """Implementa RNF-06 · firmas propias para HEIC y MP4, y después `puremagic`.

    `puremagic` no reconoce las marcas `mif1` y `msf1` de HEIC (E-3), así que el `ftyp` se resuelve
    antes. `puremagic` ordena las candidatas por confianza descendente (E-3); a la lista blanca
    solo entran las de máxima confianza (RNF-06, PA-T59.14). Si ninguna de ellas está en
    `EXTENSIONES`, el respaldo recorre todas las candidatas, pero una de menor confianza solo aporta
    su `mime_type` si este queda fuera de la lista blanca: así una firma débil no cuela un tipo
    admitido. Sin candidatas, el tipo es `application/octet-stream`.
    """
    propio = _firma_propia(cabecera)
    if propio is not None:
        return propio
    try:
        candidatas = puremagic.magic_string(cabecera)
    except (PureError, PureValueError):
        return TIPO_OCTETO
    if candidatas:
        maxima = candidatas[0].confidence
        for candidata in candidatas:
            if candidata.confidence == maxima and candidata.extension in EXTENSIONES:
                return EXTENSIONES[candidata.extension]
    for candidata in candidatas:
        if candidata.mime_type and (
            candidata.confidence == maxima or candidata.mime_type not in tipos_admitidos()
        ):
            return str(candidata.mime_type)
    return TIPO_OCTETO


def _firma_propia(cabecera: bytes) -> str | None:
    """Reconoce el contenedor ISO BMFF (`ftyp` en el byte 4): HEIC si la marca es de HEIC, MP4 si no.

    Un contenedor RIFF solo es WebP si lleva `WEBP` en los bytes 8 a 11; AVI, WAV y los demás RIFF
    salen como `application/octet-stream` para que no entren por la lista blanca (RNF-06).
    """
    if cabecera[:4] == b"RIFF":
        return TIPO_WEBP if cabecera[8:12] == b"WEBP" else TIPO_OCTETO
    if len(cabecera) < 12 or cabecera[4:8] != b"ftyp":
        return None
    return TIPO_HEIC if cabecera[8:12] in _MARCAS_HEIC else TIPO_MP4


def _nombre_local(etiqueta: str) -> str:
    """Quita el espacio de nombres de una etiqueta `{espacio}nombre`."""
    return etiqueta.rsplit("}", 1)[-1]
