"""TKT-059 · fila 3, dominio puro de `archivos`: TC-47 a TC-50 y el test de pureza.

Sin Docker ni base de datos. Prueba `cimenta/archivos/dominio/`: `tipos.py`, `declaracion.py` y
`confirmacion.py`. Las reglas reciben valores ya materializados: los instantes llegan como
enteros o como `datetime` con zona (el protocolo `Ordenable` no fija el tipo) y el reloj lo pone
`aplicacion/` (regla 2 de CLAUDE.md, ADR-021).

Los símbolos del dominio se importan dentro de cada caso, no al principio del módulo: así un fallo
es de la prueba y no de la colección, y ningún caso enmascara a otro.

Trazas: `CA-3`, `CA-5`, `CA-6`, `CA-7`, `CA-8`, `RNF-06` y `PA-T59.13`. Ninguna regla de este
archivo tiene `RN-xx` en el PRD.
"""

from __future__ import annotations

import ast
import sys
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from cimenta.archivos.dominio.declaracion import DefectoDeclaracion

BACKEND = Path(__file__).resolve().parents[1]
DOMINIO_ARCHIVOS = BACKEND / "cimenta" / "archivos" / "dominio"
ARCHIVOS_ESPERADOS = frozenset({"tipos.py", "declaracion.py", "confirmacion.py"})
PAQUETE_PROPIO = "cimenta.archivos.dominio"
PAQUETE_TIPOS_BASE = "tipos_base"
# Módulos de E/S y de reloj que la lista blanca de la biblioteca estándar excluye (ADR-021).
RELOJ_Y_ES = frozenset(
    {
        "datetime",
        "os",
        "socket",
        "time",
        "pathlib",
        "io",
        "random",
        "subprocess",
        "tempfile",
        "shutil",
        "asyncio",
        "threading",
        "http",
        "urllib",
        "ssl",
    }
)
PROHIBIDOS_NOMBRADOS = frozenset({"datetime", "os", "socket"})

SOLICITANTE = uuid.UUID("11111111-1111-4111-8111-111111111111")
OTRA_PERSONA = uuid.UUID("22222222-2222-4222-8222-222222222222")
VENCE_EN = 100  # vencimiento entero de los casos de TC-47

NOMBRE_VALIDO = "Presupuesto torre 5.xlsx"
TAMANO_VALIDO = 8388608  # 8 MiB: bajo el límite de documentos
HASH_VALIDO = "3f" * 32  # 64 caracteres hexadecimales en minúsculas
TIPO_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
LIMITE_IMAGEN = 15728640  # 15 MiB
LIMITE_VIDEO = 52428800  # 50 MiB
LIMITE_DOCUMENTO = 26214400  # 25 MiB

HASH_DECLARADO = "a" * 64
OTRO_HASH = "b" * 64
TAMANO_DECLARADO = 8388608

MSG_OBLIGATORIO = "El campo es obligatorio."
MSG_DEMASIADO_LARGO = "El nombre admite hasta 255 caracteres."
MSG_NO_POSITIVO = "El tamaño debe ser mayor que cero."
MSG_FORMATO_HASH = "El SHA-256 son 64 caracteres hexadecimales en minúsculas."
MSG_VALOR_NO_PERMITIDO = (
    "El tipo de archivo no está permitido. Se admiten JPEG, PNG, HEIC, WebP, MP4, PDF, XML y XLSX."
)

TIPOS_ESPERADOS = (
    ("image/jpeg", "IMAGEN", "inline"),
    ("image/png", "IMAGEN", "inline"),
    ("image/heic", "IMAGEN", "inline"),
    ("image/webp", "IMAGEN", "inline"),
    ("video/mp4", "VIDEO", "inline"),
    ("application/pdf", "DOCUMENTO", "attachment"),
    ("application/xml", "DOCUMENTO", "attachment"),
    (TIPO_XLSX, "DOCUMENTO", "attachment"),
)


# --- TC-47 · evaluar_previa ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("estado", "solicitante", "ahora", "esperado"),
    [
        # El solicitante va antes que el estado: un 403 no revela en qué estado está el archivo.
        ("PENDIENTE", "AJENO", 50, "NO_ES_SOLICITANTE"),
        ("PENDIENTE", "AJENO", 101, "NO_ES_SOLICITANTE"),
        ("DISPONIBLE", "AJENO", 50, "NO_ES_SOLICITANTE"),
        ("CADUCADO", "AJENO", 50, "NO_ES_SOLICITANTE"),
        ("ANULADO", "AJENO", 50, "NO_ES_SOLICITANTE"),
        # YA_DISPONIBLE no caduca: el vencimiento solo mira a PENDIENTE.
        ("DISPONIBLE", "PROPIO", 50, "YA_DISPONIBLE"),
        ("DISPONIBLE", "PROPIO", 101, "YA_DISPONIBLE"),
        # CADUCADO y ANULADO ganan a VENCIDO aunque el instante ya pasó del vencimiento.
        ("CADUCADO", "PROPIO", 50, "CADUCADO"),
        ("CADUCADO", "PROPIO", 101, "CADUCADO"),
        ("ANULADO", "PROPIO", 50, "NO_CONFIRMABLE"),
        ("ANULADO", "PROPIO", 101, "NO_CONFIRMABLE"),
        # PENDIENTE se confirma hasta vence_en inclusive; un instante después, VENCIDO.
        ("PENDIENTE", "PROPIO", 50, "CONFIRMABLE"),
        ("PENDIENTE", "PROPIO", 99, "CONFIRMABLE"),
        ("PENDIENTE", "PROPIO", 100, "CONFIRMABLE"),
        ("PENDIENTE", "PROPIO", 101, "VENCIDO"),
        ("PENDIENTE", "PROPIO", 1000, "VENCIDO"),
    ],
)
def test_tkt059_dominio_evaluar_previa(
    estado: str, solicitante: str, ahora: int, esperado: str
) -> None:
    """TC-47 · CA-7 esc. 2, 3 y 4 — orden de `evaluar_previa`: NO_ES_SOLICITANTE > YA_DISPONIBLE >
    CADUCADO > NO_CONFIRMABLE > VENCIDO > CONFIRMABLE; en `ahora == vence_en` el archivo se confirma."""
    from cimenta.archivos.dominio.confirmacion import EstadoArchivo, PasoPrevio, evaluar_previa

    resultado = evaluar_previa(
        estado=EstadoArchivo(estado),
        subido_por_id=SOLICITANTE,
        usuario_id=SOLICITANTE if solicitante == "PROPIO" else OTRA_PERSONA,
        ahora=ahora,
        vence_en=VENCE_EN,
    )

    assert resultado is PasoPrevio(esperado)


def test_tkt059_dominio_evaluar_previa_con_datetime() -> None:
    """TC-47 · CA-7 esc. 3 — con `datetime` con zona el mismo borde: en `vence_en` se confirma y un
    segundo después caduca por vencimiento. El dominio no importa `datetime`; lo recibe."""
    from datetime import UTC, datetime, timedelta

    from cimenta.archivos.dominio.confirmacion import EstadoArchivo, PasoPrevio, evaluar_previa

    vence_en = datetime(2026, 11, 10, 9, 0, tzinfo=UTC)
    un_segundo = timedelta(seconds=1)

    def paso(ahora: datetime) -> PasoPrevio:
        return evaluar_previa(
            estado=EstadoArchivo.PENDIENTE,
            subido_por_id=SOLICITANTE,
            usuario_id=SOLICITANTE,
            ahora=ahora,
            vence_en=vence_en,
        )

    assert paso(vence_en - un_segundo) is PasoPrevio.CONFIRMABLE
    assert paso(vence_en) is PasoPrevio.CONFIRMABLE
    assert paso(vence_en + un_segundo) is PasoPrevio.VENCIDO


# --- TC-48 · comparar_objeto ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("objeto", "esperado"),
    [
        (None, "NO_SUBIDO"),
        ((TAMANO_DECLARADO, HASH_DECLARADO), None),
        ((8126464, HASH_DECLARADO), "TAMANO_DISTINTO"),
        ((8126464, OTRO_HASH), "TAMANO_DISTINTO"),
        ((8126464, None), "TAMANO_DISTINTO"),
        ((TAMANO_DECLARADO, OTRO_HASH), "HASH_DISTINTO"),
        ((TAMANO_DECLARADO, None), "HASH_DISTINTO"),
    ],
)
def test_tkt059_dominio_comparar_objeto(
    objeto: tuple[int, str | None] | None, esperado: str | None
) -> None:
    """TC-48 · CA-5 esc. 1 y 2, CA-7 esc. 1 — `None` es NO_SUBIDO; el tamaño se compara antes que el
    hash, y una suma ausente (P-11) cuenta como distinta; todo igual devuelve `None`."""
    from cimenta.archivos.dominio.confirmacion import (
        Discrepancia,
        ObjetoAlmacenado,
        comparar_objeto,
    )

    almacenado = (
        None if objeto is None else ObjetoAlmacenado(tamano_bytes=objeto[0], sha256_hex=objeto[1])
    )
    resultado = comparar_objeto(
        tamano_declarado=TAMANO_DECLARADO, hash_declarado=HASH_DECLARADO, objeto=almacenado
    )

    if esperado is None:
        assert resultado is None
    else:
        assert resultado is Discrepancia(esperado)


# --- TC-49 · evaluar_declaracion -----------------------------------------------------------------


def _evaluar(
    *,
    nombre: str = NOMBRE_VALIDO,
    tamano: int = TAMANO_VALIDO,
    hash_sha256: str = HASH_VALIDO,
    tipo: str = TIPO_XLSX,
    campo_raiz: str = "archivo",
) -> tuple[DefectoDeclaracion, ...]:
    """Evalúa la declaración válida salvo lo que se cambia. Devuelve lo que devuelve la regla."""
    from cimenta.archivos.dominio.declaracion import LimitesArchivo, evaluar_declaracion

    return evaluar_declaracion(
        nombre_original=nombre,
        tamano_bytes=tamano,
        hash_sha256=hash_sha256,
        tipo_declarado=tipo,
        limites=LimitesArchivo(
            imagen_bytes=LIMITE_IMAGEN,
            video_bytes=LIMITE_VIDEO,
            documento_bytes=LIMITE_DOCUMENTO,
        ),
        campo_raiz=campo_raiz,
    )


def _defecto(campo: str, codigo: str, mensaje: str) -> DefectoDeclaracion:
    from cimenta.archivos.dominio.declaracion import DefectoDeclaracion

    return DefectoDeclaracion(campo=campo, codigo=codigo, mensaje=mensaje)


def test_tkt059_dominio_evaluar_declaracion_valida_no_produce_defectos() -> None:
    """TC-49 · CA-3 · feliz — un XLSX de 8 MiB con hash en minúsculas no produce defectos."""
    assert _evaluar() == ()


@pytest.mark.parametrize(
    ("cambios", "campo", "codigo", "mensaje"),
    [
        ({"nombre": ""}, "archivo.nombre_original", "OBLIGATORIO", MSG_OBLIGATORIO),
        ({"nombre": "  "}, "archivo.nombre_original", "OBLIGATORIO", MSG_OBLIGATORIO),
        ({"nombre": "a" * 256}, "archivo.nombre_original", "DEMASIADO_LARGO", MSG_DEMASIADO_LARGO),
        ({"tamano": 0}, "archivo.tamano_bytes", "NO_POSITIVO", MSG_NO_POSITIVO),
        ({"tamano": -1}, "archivo.tamano_bytes", "NO_POSITIVO", MSG_NO_POSITIVO),
        ({"hash_sha256": "3F" * 32}, "archivo.hash_sha256", "FORMATO", MSG_FORMATO_HASH),
        ({"hash_sha256": "3f" * 31 + "3"}, "archivo.hash_sha256", "FORMATO", MSG_FORMATO_HASH),
        # `$` de una expresión regular admite un salto final; el formato exige la cadena entera.
        ({"hash_sha256": HASH_VALIDO + "\n"}, "archivo.hash_sha256", "FORMATO", MSG_FORMATO_HASH),
        (
            {"tipo": "text/xml"},
            "archivo.tipo_declarado",
            "VALOR_NO_PERMITIDO",
            MSG_VALOR_NO_PERMITIDO,
        ),
        (
            {"tamano": LIMITE_DOCUMENTO + 1},
            "archivo.tamano_bytes",
            "FUERA_DE_RANGO",
            "El archivo excede el límite de 26214400 bytes (25 MB) para documentos.",
        ),
    ],
)
def test_tkt059_dominio_evaluar_declaracion(
    cambios: dict[str, Any], campo: str, codigo: str, mensaje: str
) -> None:
    """TC-49 · CA-3 esc. 1 a 3 — cada defecto sale solo, con su campo, su código y su mensaje
    exactos; el resto de la declaración es válido."""
    assert _evaluar(**cambios) == (_defecto(campo, codigo, mensaje),)


@pytest.mark.parametrize(
    ("tipo", "limite", "mensaje"),
    [
        (
            "image/jpeg",
            LIMITE_IMAGEN,
            "El archivo excede el límite de 15728640 bytes (15 MB) para imágenes.",
        ),
        (
            "image/png",
            LIMITE_IMAGEN,
            "El archivo excede el límite de 15728640 bytes (15 MB) para imágenes.",
        ),
        (
            "image/heic",
            LIMITE_IMAGEN,
            "El archivo excede el límite de 15728640 bytes (15 MB) para imágenes.",
        ),
        (
            "image/webp",
            LIMITE_IMAGEN,
            "El archivo excede el límite de 15728640 bytes (15 MB) para imágenes.",
        ),
        (
            "video/mp4",
            LIMITE_VIDEO,
            "El archivo excede el límite de 52428800 bytes (50 MB) para videos.",
        ),
        (
            "application/pdf",
            LIMITE_DOCUMENTO,
            "El archivo excede el límite de 26214400 bytes (25 MB) para documentos.",
        ),
        (
            "application/xml",
            LIMITE_DOCUMENTO,
            "El archivo excede el límite de 26214400 bytes (25 MB) para documentos.",
        ),
        (
            TIPO_XLSX,
            LIMITE_DOCUMENTO,
            "El archivo excede el límite de 26214400 bytes (25 MB) para documentos.",
        ),
    ],
)
def test_tkt059_dominio_evaluar_declaracion_limite_por_categoria(
    tipo: str, limite: int, mensaje: str
) -> None:
    """TC-49 · CA-3 esc. 2 — el tamaño igual al límite de su categoría se admite; un byte más se
    rechaza con el límite y la categoría de ese tipo (imagen, video o documento)."""
    assert _evaluar(tipo=tipo, tamano=limite) == ()
    assert _evaluar(tipo=tipo, tamano=limite + 1) == (
        _defecto("archivo.tamano_bytes", "FUERA_DE_RANGO", mensaje),
    )


@pytest.mark.parametrize("tipo", ["image/svg+xml", "text/xml", "application/zip"])
def test_tkt059_dominio_evaluar_declaracion_tipo_invalido_no_da_error_de_tamano(tipo: str) -> None:
    """TC-49 · CA-3 esc. 3 — un tipo fuera de la lista no tiene límite: con un tamaño enorme solo
    sale `VALOR_NO_PERMITIDO`, sin `FUERA_DE_RANGO`."""
    assert _evaluar(tipo=tipo, tamano=10**9) == (
        _defecto("archivo.tipo_declarado", "VALOR_NO_PERMITIDO", MSG_VALOR_NO_PERMITIDO),
    )


def test_tkt059_dominio_evaluar_declaracion_varios_defectos_en_orden_de_la_tabla() -> None:
    """TC-49 · CA-3 — varios defectos a la vez salen en el orden de la tabla de campos."""
    assert _evaluar(nombre="  ", tamano=0, hash_sha256="ABC", tipo="text/xml") == (
        _defecto("archivo.nombre_original", "OBLIGATORIO", MSG_OBLIGATORIO),
        _defecto("archivo.tamano_bytes", "NO_POSITIVO", MSG_NO_POSITIVO),
        _defecto("archivo.hash_sha256", "FORMATO", MSG_FORMATO_HASH),
        _defecto("archivo.tipo_declarado", "VALOR_NO_PERMITIDO", MSG_VALOR_NO_PERMITIDO),
    )
    # FUERA_DE_RANGO es el último campo de la tabla: sale después del formato del hash.
    assert _evaluar(nombre="a" * 256, hash_sha256="3f" * 31 + "3", tamano=LIMITE_DOCUMENTO + 1) == (
        _defecto("archivo.nombre_original", "DEMASIADO_LARGO", MSG_DEMASIADO_LARGO),
        _defecto("archivo.hash_sha256", "FORMATO", MSG_FORMATO_HASH),
        _defecto(
            "archivo.tamano_bytes",
            "FUERA_DE_RANGO",
            "El archivo excede el límite de 26214400 bytes (25 MB) para documentos.",
        ),
    )
    # Tipo no admitido: no hay límite de categoría, así que no aparece FUERA_DE_RANGO.
    assert _evaluar(tamano=-5, hash_sha256="", tipo="image/jpg") == (
        _defecto("archivo.tamano_bytes", "NO_POSITIVO", MSG_NO_POSITIVO),
        _defecto("archivo.hash_sha256", "FORMATO", MSG_FORMATO_HASH),
        _defecto("archivo.tipo_declarado", "VALOR_NO_PERMITIDO", MSG_VALOR_NO_PERMITIDO),
    )


def test_tkt059_dominio_evaluar_declaracion_bordes_de_forma_admitidos() -> None:
    """TC-49 · CA-3 — el nombre admite 255 caracteres (no bytes), el tamaño 1 byte y el hash los 64
    caracteres de todas las cifras hexadecimales en minúsculas."""
    assert _evaluar(nombre="a" * 255) == ()
    assert _evaluar(nombre="ñ" * 255) == ()
    assert _evaluar(tamano=1) == ()
    assert _evaluar(hash_sha256="0123456789abcdef" * 4) == ()


def test_tkt059_dominio_evaluar_declaracion_tipo_exacto_tras_strip_y_minusculas() -> None:
    """TC-49 · CA-3 esc. 3, P-12 — el tipo declarado se compara tras `strip()` y `lower()`: el
    espacio y las mayúsculas no cambian el tipo."""
    assert _evaluar(tipo=" Image/JPEG ") == ()


@pytest.mark.parametrize("tipo", ["text/xml", "image/jpg", "image/heif", "image/svg+xml"])
def test_tkt059_dominio_evaluar_declaracion_tipo_sin_alias(tipo: str) -> None:
    """TC-49 · CA-3 esc. 3, P-12 — sin alias: `text/xml`, `image/jpg` e `image/heif` se rechazan
    con `VALOR_NO_PERMITIDO` en el campo del tipo, y el SVG también."""
    assert _evaluar(tipo=tipo) == (
        _defecto("archivo.tipo_declarado", "VALOR_NO_PERMITIDO", MSG_VALOR_NO_PERMITIDO),
    )


def test_tkt059_dominio_evaluar_declaracion_campo_raiz_prefija_los_campos() -> None:
    """TC-49 · CA-3 — `campo_raiz` es el prefijo de cada campo del defecto; el caso de uso pasa
    `archivo`, el nombre de la propiedad en `ImportacionNueva`."""
    assert _evaluar(nombre="", campo_raiz="declaracion") == (
        _defecto("declaracion.nombre_original", "OBLIGATORIO", MSG_OBLIGATORIO),
    )


MSG_NOMBRE_NO_PERMITIDO = "El nombre contiene caracteres no permitidos."


@pytest.mark.parametrize(
    "nombre",
    [
        pytest.param("\x00Presupuesto.xlsx", id="nul_al_inicio"),
        pytest.param("Presu\x00puesto.xlsx", id="nul_en_medio"),
        pytest.param("Presupuesto.xlsx\x00", id="nul_al_final"),
        pytest.param("\x00", id="solo_nul"),
        pytest.param("Presu\x00pues\x00to.xlsx", id="varios_nul"),
        pytest.param("a\ud800b", id="sustituto_alto_solitario"),
        pytest.param("a\udc00b", id="sustituto_bajo_solitario"),
        pytest.param("a\udfffb", id="sustituto_ultimo_u_dfff"),
        pytest.param("\ud800", id="solo_un_sustituto"),
        pytest.param("a\ud83d\ude00b", id="par_sustituto_sin_combinar"),
        pytest.param("a\x00b\ud800c", id="nul_y_sustituto_a_la_vez"),
    ],
)
def test_tkt059_ca03_dominio_nombre_con_nul_o_sustituto_se_rechaza(nombre: str) -> None:
    """TC-49 · CA-3 · RNF-06 — un NUL o un sustituto Unicode (U+D800 a U+DFFF) en el nombre produce
    un solo defecto `FORMATO` en `nombre_original`, con el mensaje exacto; es regla de forma, sin RN."""
    assert _evaluar(nombre=nombre) == (
        _defecto("archivo.nombre_original", "FORMATO", MSG_NOMBRE_NO_PERMITIDO),
    )


@pytest.mark.parametrize(
    "nombre",
    [
        pytest.param("Presupuesto ñandú torre 5 😀 final.xlsx", id="tildes_emoji_y_espacios"),
        pytest.param("퟿a", id="u_d7ff_justo_antes_de_los_sustitutos"),
        pytest.param("a", id="u_e000_justo_despues_de_los_sustitutos"),
        pytest.param("a\u0001b\u001fc", id="otros_controles_no_son_nul"),
        pytest.param("日本語 \U0001f600\U0010ffff.pdf", id="planos_astrales_validos"),
    ],
)
def test_tkt059_ca03_dominio_nombre_valido_no_produce_defectos(nombre: str) -> None:
    """TC-49 · CA-3 — el rechazo es solo de NUL y sustitutos: tildes, emoji, espacios, los bordes
    U+D7FF y U+E000 y otros controles distintos de NUL no producen defecto."""
    assert _evaluar(nombre=nombre) == ()


def test_tkt059_ca03_dominio_nombre_con_nul_respeta_el_orden_de_la_tabla() -> None:
    """TC-49 · CA-3 — orden de la tabla: el defecto del nombre con NUL va después de los otros
    defectos de `nombre_original` y antes de los de `tamano_bytes`, `hash_sha256` y el tipo."""
    # Con DEMASIADO_LARGO el nombre incumple dos reglas: salen las dos, en este orden.
    assert _evaluar(nombre="\x00" + "a" * 255) == (
        _defecto("archivo.nombre_original", "DEMASIADO_LARGO", MSG_DEMASIADO_LARGO),
        _defecto("archivo.nombre_original", "FORMATO", MSG_NOMBRE_NO_PERMITIDO),
    )
    # Con el resto de los campos inválidos, el nombre va primero y el tamaño después.
    assert _evaluar(nombre="a\x00b", tamano=0, hash_sha256="ABC", tipo="text/xml") == (
        _defecto("archivo.nombre_original", "FORMATO", MSG_NOMBRE_NO_PERMITIDO),
        _defecto("archivo.tamano_bytes", "NO_POSITIVO", MSG_NO_POSITIVO),
        _defecto("archivo.hash_sha256", "FORMATO", MSG_FORMATO_HASH),
        _defecto("archivo.tipo_declarado", "VALOR_NO_PERMITIDO", MSG_VALOR_NO_PERMITIDO),
    )
    # Todo junto: nombre largo con NUL, hash inválido y tamaño sobre el límite.
    assert _evaluar(
        nombre="a\ud800" + "b" * 255, hash_sha256="3f" * 31 + "3", tamano=LIMITE_DOCUMENTO + 1
    ) == (
        _defecto("archivo.nombre_original", "DEMASIADO_LARGO", MSG_DEMASIADO_LARGO),
        _defecto("archivo.nombre_original", "FORMATO", MSG_NOMBRE_NO_PERMITIDO),
        _defecto("archivo.hash_sha256", "FORMATO", MSG_FORMATO_HASH),
        _defecto(
            "archivo.tamano_bytes",
            "FUERA_DE_RANGO",
            "El archivo excede el límite de 26214400 bytes (25 MB) para documentos.",
        ),
    )


def test_tkt059_ca03_dominio_nombre_con_nul_respeta_campo_raiz() -> None:
    """TC-49 · CA-3 — con otro `campo_raiz`, el defecto del nombre con NUL cuelga de ese prefijo."""
    assert _evaluar(nombre="a\x00b", campo_raiz="declaracion") == (
        _defecto("declaracion.nombre_original", "FORMATO", MSG_NOMBRE_NO_PERMITIDO),
    )


def test_tkt059_ca03_dominio_nombre_en_blanco_no_se_confunde_con_nul() -> None:
    """TC-49 · CA-3 — un nombre vacío o en blanco sigue siendo `OBLIGATORIO` y solo eso; el NUL no
    cuenta como espacio en blanco, así que `"  \\x00"` no es `OBLIGATORIO`."""
    assert _evaluar(nombre="  ") == (
        _defecto("archivo.nombre_original", "OBLIGATORIO", MSG_OBLIGATORIO),
    )
    assert _evaluar(nombre="  \x00") == (
        _defecto("archivo.nombre_original", "FORMATO", MSG_NOMBRE_NO_PERMITIDO),
    )


# --- TC-50 · tipos y disposición -----------------------------------------------------------------


def test_tkt059_dominio_tipos_y_disposicion_catalogo_en_orden() -> None:
    """TC-50 · CA-6, CA-8 — la lista blanca tiene ocho tipos, en este orden, cada uno con su
    categoría; `TIPO_XLSX` es el MIME del libro de Excel."""
    from cimenta.archivos.dominio.tipos import TIPO_XLSX as tipo_xlsx
    from cimenta.archivos.dominio.tipos import TIPOS_ADMITIDOS, CategoriaArchivo, tipos_admitidos

    assert tipos_admitidos() == tuple(tipo for tipo, _, _ in TIPOS_ESPERADOS)
    assert [(tipo, str(categoria)) for tipo, categoria in TIPOS_ADMITIDOS] == [
        (tipo, categoria) for tipo, categoria, _ in TIPOS_ESPERADOS
    ]
    assert {str(categoria) for categoria in CategoriaArchivo} == {"IMAGEN", "VIDEO", "DOCUMENTO"}
    assert tipo_xlsx == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.mark.parametrize(("tipo", "categoria", "disposicion"), TIPOS_ESPERADOS)
def test_tkt059_dominio_tipos_y_disposicion_por_tipo(
    tipo: str, categoria: str, disposicion: str
) -> None:
    """TC-50 · CA-6, CA-8 — cada tipo admitido tiene su categoría y su disposición: `inline` solo
    para imagen y video; PDF, XML y XLSX son `attachment`."""
    from cimenta.archivos.dominio.tipos import (
        CategoriaArchivo,
        categoria_de,
        disposicion_de,
        tipo_admitido,
    )

    assert tipo_admitido(tipo) is True
    assert categoria_de(tipo) is CategoriaArchivo(categoria)
    assert disposicion_de(tipo) == disposicion


@pytest.mark.parametrize(
    "tipo",
    [
        "image/svg+xml",
        "application/zip",
        "text/xml",
        "image/jpg",
        "image/heif",
        "application/vnd.ms-excel",
        "application/x-msdownload",
        "image/gif",
        "video/quicktime",
        "",
    ],
)
def test_tkt059_dominio_tipos_y_disposicion_rechaza_lo_no_listado(tipo: str) -> None:
    """TC-50 · CA-6 esc. 2 y 3, RNF-06 — el SVG (prohibido) y el ZIP no están admitidos, y tampoco
    los alias ni los tipos de Excel antiguos: ni tipo admitido ni categoría."""
    from cimenta.archivos.dominio.tipos import categoria_de, tipo_admitido

    assert tipo_admitido(tipo) is False
    assert categoria_de(tipo) is None


# --- Pureza de la capa (regla 2 de CLAUDE.md, ADR-021) -------------------------------------------


def _modulos_importados(archivo: Path) -> list[str]:
    """Módulos que importa `archivo`. Las importaciones relativas al propio paquete no cuentan; las
    que salen de él (`..`), sí."""
    arbol = ast.parse(archivo.read_text(encoding="utf-8"), filename=str(archivo))
    modulos: list[str] = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            modulos.extend(alias.name for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom):
            if nodo.level == 0:
                modulos.append(nodo.module or "")
            elif nodo.level > 1:
                modulos.append(f"..{nodo.module or ''}")
    return modulos


def _permitido(modulo: str) -> bool:
    """Biblioteca estándar sin E/S ni reloj, `tipos_base` y el propio paquete."""
    raiz = modulo.split(".")[0]
    if modulo.startswith(PAQUETE_PROPIO) or raiz == PAQUETE_TIPOS_BASE:
        return True
    return raiz in sys.stdlib_module_names and raiz not in RELOJ_Y_ES


def test_tkt059_pureza_dominio_archivos_solo_biblioteca_estandar_y_tipos_base() -> None:
    """Regla 2 de CLAUDE.md · ADR-021 · RNF-06 — `cimenta/archivos/dominio/` importa solo la
    biblioteca estándar sin E/S ni reloj, `tipos_base` y su propio paquete."""
    archivos = sorted(DOMINIO_ARCHIVOS.glob("*.py"))
    nombres = {archivo.name for archivo in archivos}

    # Anti-verde vacío: con la carpeta sin los tres módulos, el recorrido no revisaría nada.
    assert nombres >= ARCHIVOS_ESPERADOS, (
        f"Faltan archivos en cimenta/archivos/dominio/: {sorted(ARCHIVOS_ESPERADOS - nombres)}"
    )
    prohibidos = {
        archivo.name: [modulo for modulo in _modulos_importados(archivo) if not _permitido(modulo)]
        for archivo in archivos
    }
    assert {nombre: mods for nombre, mods in prohibidos.items() if mods} == {}, (
        "El dominio de archivos solo importa biblioteca estándar sin E/S ni reloj, tipos_base y "
        "su paquete"
    )


def test_tkt059_pureza_dominio_archivos_sin_datetime_os_ni_socket() -> None:
    """Regla 2 de CLAUDE.md · ADR-021 · RNF-06 — ningún archivo de `cimenta/archivos/dominio/`
    importa `datetime`, `os` ni `socket`: el instante y el vencimiento llegan como argumentos."""
    archivos = sorted(DOMINIO_ARCHIVOS.glob("*.py"))
    nombres = {archivo.name for archivo in archivos}

    assert nombres >= ARCHIVOS_ESPERADOS, (
        f"Faltan archivos en cimenta/archivos/dominio/: {sorted(ARCHIVOS_ESPERADOS - nombres)}"
    )
    hallados = {
        archivo.name: sorted(
            {modulo.split(".")[0] for modulo in _modulos_importados(archivo)} & PROHIBIDOS_NOMBRADOS
        )
        for archivo in archivos
    }
    assert {nombre: mods for nombre, mods in hallados.items() if mods} == {}
