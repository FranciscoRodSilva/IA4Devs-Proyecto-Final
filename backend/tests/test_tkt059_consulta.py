"""Consulta y descarga de un archivo por la API (TKT-059, fila 14): TC-31, TC-32 y TC-34 a TC-36.

`GET /api/v1/archivos/{archivo_id}` devuelve los metadatos y `GET /api/v1/archivos/{archivo_id}/descarga`
emite una URL prefirmada de lectura de vida corta (ADR-016): el servidor firma y se aparta, los bytes nunca
pasan por la API. Las dos rutas son de `DIRECCION_GENERAL` y `DIRECTOR_PROYECTOS` (`x-roles` del borrador) y
el rol se comprueba **al emitir**: durante su vida la URL es la credencial, así que quien no tiene el rol no
recibe ninguna URL ni la firma el almacén (un espía sobre `url_lectura` lo demuestra).

Cada rechazo se prueba con el contrato de error completo —`tipo`, `codigo` o `motivo`, `mensaje` literal del
diseño, `detalle` con sus valores, `acciones` y `correlacion_id`— y, después, con una fotografía de lo que no
debió cambiar. Además de TC-31 a TC-36 hay una defensa de `O-4` de seguridad: la URL lleva firmados el tipo
y la disposición de la respuesta, un XML y un `.xlsx` se sirven siempre como `attachment`, y el
`Content-Type` que entrega el almacén es el de la fila aunque el objeto tenga otro.

PostgreSQL y MinIO reales con testcontainers: el esquema sale de `alembic upgrade head`, las escrituras van
con el rol de aplicación, y los archivos `DISPONIBLE` se obtienen por la API real (alta, `PUT` por la URL
prefirmada y confirmación). Las altas se hacen **dentro** del bloque `with TestClient(...)` que abre la
fixture `escena` (preámbulo del plan de pruebas). Ningún `sleep`.

TC-33 (la URL caduca) ya lo cubre `test_tkt059_almacen.py` y no se repite. El diseño no declara ningún
control de asignación de obra sobre estas lecturas, y en el sistema no existe aún un vínculo usuario-obra,
así que no hay un test de «otra obra»: ver el informe de la fila 14.
"""

from __future__ import annotations

import io
import uuid
import zipfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qsl, quote, urlencode, urlsplit

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from herramientas.soporte_tkt017_api import (
    CABECERA_CORRELACION,
    CONTRASENA_DE_PRUEBA,
    NOMBRE_DEL_DIRECTOR,
    borrador,
    exigir_error,
    iniciar_sesion,
    leer,
    validar_contra,
)
from herramientas.soporte_tkt059 import (
    NOMBRE_DEL_LIBRO,
    TIPO_XLSX,
    AlmacenContador,
    ArchivoSubido,
    Respuesta,
    abrir_sesion_del_director,
    asientos_del_archivo,
    cliente_https,
    confirmar_por_http,
    crear_aplicacion_de_archivos,
    dar_de_alta,
    sembrar_director,
    subir_objeto,
)

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta.
    from conftest import RelojDePrueba, SembrarUsuario
    from mypy_boto3_s3 import S3Client

    from cimenta.archivos.infraestructura.almacen_s3 import AlmacenS3

# --------------------------------------------------------------------------- literales del diseño

MENSAJE_NO_DISPONIBLE = "El archivo todavía no está disponible."
MENSAJE_CADUCADO_AL_DESCARGAR = "La subida del archivo caducó y no se puede descargar."
MENSAJE_NO_EXISTE = "El archivo no existe."
MENSAJE_ROL_INSUFICIENTE = "Tu rol no permite esta operación."
MENSAJE_SIN_SESION = "No hay una sesión iniciada."

# Los `x-roles` de las dos operaciones del borrador, en su orden.
ROLES_DE_CONSULTA = ["DIRECCION_GENERAL", "DIRECTOR_PROYECTOS"]
ROLES_SIN_PERMISO = ["COMPRAS", "RESIDENTE", "ALMACEN", "ADMINISTRACION"]
VIDA_DE_LA_URL_DE_LECTURA = timedelta(minutes=5)
TIPO_PDF = "application/pdf"
TIPO_JPEG = "image/jpeg"
TIPO_XML = "application/xml"
LIMITE_DE_LECTURA_SEGUNDOS = 30.0

SQL_DENEGACIONES = (
    "SELECT usuario_id, ocurrido_en, motivo, regla_negocio, entidad_tipo, entidad_id, obra_id, "
    "datos_antes IS NULL AS datos_antes_es_nulo, datos_despues "
    "FROM bitacora WHERE accion::text = 'DENEGAR' ORDER BY ocurrido_en, id"
)


def ruta_de_metadatos(archivo_id: uuid.UUID) -> str:
    return f"/api/v1/archivos/{archivo_id}"


def ruta_de_descarga(archivo_id: uuid.UUID) -> str:
    return f"/api/v1/archivos/{archivo_id}/descarga"


# Las dos operaciones `GET` de la fila, para los casos que valen igual en las dos.
AMBAS_RUTAS = [
    pytest.param(ruta_de_metadatos, id="obtener_archivo"),
    pytest.param(ruta_de_descarga, id="obtener_url_descarga_archivo"),
]
AMBOS_ROLES = [pytest.param(rol, id=rol) for rol in ROLES_DE_CONSULTA]


# --------------------------------------------------------------------------- contenidos


def _content_types(*sobrescrituras: tuple[str, str]) -> bytes:
    cabecera = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" '
        'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
    )
    partes = "".join(
        f'<Override PartName="{parte}" ContentType="{tipo}"/>' for parte, tipo in sobrescrituras
    )
    return (cabecera + partes + "</Types>").encode("utf-8")


def _xlsx_minimo() -> bytes:
    """Un libro mínimo que el detector reconoce como `.xlsx`: confirmable si nada lo impide."""
    memoria = io.BytesIO()
    with zipfile.ZipFile(memoria, "w") as archivo_zip:
        archivo_zip.writestr(
            "[Content_Types].xml",
            _content_types(
                (
                    "/xl/workbook.xml",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml",
                )
            ),
            compress_type=zipfile.ZIP_DEFLATED,
        )
        archivo_zip.writestr("xl/workbook.xml", b"<workbook/>", compress_type=zipfile.ZIP_DEFLATED)
    return memoria.getvalue()


def _pdf() -> bytes:
    return b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"


def _jpeg() -> bytes:
    return b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00" + b"\x00" * 64


def _xml() -> bytes:
    return b'<?xml version="1.0" encoding="UTF-8"?>\n<comprobante version="4.0"/>\n'


@dataclass(frozen=True)
class Documento:
    """Un contenido admitido con el tipo que se declara y la disposición que la lista blanca le asigna."""

    nombre: str
    tipo: str
    disposicion: str
    contenido: bytes


PDF = Documento("Contrato de obra.pdf", TIPO_PDF, "attachment", _pdf())
JPEG = Documento("Avance del muro.jpg", TIPO_JPEG, "inline", _jpeg())
XML = Documento("Comprobante.xml", TIPO_XML, "attachment", _xml())
XLSX = Documento(NOMBRE_DEL_LIBRO, TIPO_XLSX, "attachment", _xlsx_minimo())
DOCUMENTOS = [
    pytest.param(PDF, id="pdf"),
    pytest.param(JPEG, id="jpeg"),
    pytest.param(XML, id="xml"),
    pytest.param(XLSX, id="xlsx"),
]


# --------------------------------------------------------------------------- el espía del almacén


class AlmacenEspia(AlmacenContador):
    """El almacén contado, con la lista de URL de lectura que se firmaron.

    `url_lectura` delega en el adaptador real: una URL emitida sirve de verdad contra MinIO.
    """

    def __init__(self, real: Any) -> None:
        super().__init__(real)
        self.urls_de_lectura: list[dict[str, Any]] = []

    def url_lectura(
        self,
        clave: str,
        *,
        vida: timedelta,
        tipo_mime: str,
        nombre_original: str,
        disposicion: str,
    ) -> str:
        self.urls_de_lectura.append(
            {
                "clave": clave,
                "vida": vida,
                "tipo_mime": tipo_mime,
                "nombre_original": nombre_original,
                "disposicion": disposicion,
            }
        )
        return self.real.url_lectura(
            clave,
            vida=vida,
            tipo_mime=tipo_mime,
            nombre_original=nombre_original,
            disposicion=disposicion,
        )

    def reiniciar(self) -> None:
        self.llamadas_metadatos.clear()
        self.rangos_leidos.clear()
        self.llamadas_leer_todo.clear()
        self.reescrituras.clear()
        self.urls_de_lectura.clear()


# --------------------------------------------------------------------------- la escena


@dataclass(frozen=True)
class Fotografia:
    """Todo lo que un rechazo no debe cambiar, tal como lo ve una conexión nueva."""

    fila: dict[str, Any]
    asientos_del_archivo: list[dict[str, Any]]
    bitacora_sin_denegar: int
    denegaciones: list[dict[str, Any]]


@dataclass
class Escena:
    """La aplicación real con `archivos` montado, un cliente HTTPS abierto y un Director con sesión."""

    cliente: TestClient
    aplicacion: FastAPI
    motor: Engine
    reloj: RelojDePrueba
    almacen: AlmacenEspia
    s3: S3Client
    bucket: str
    origen_del_almacen: str
    sembrar_usuario: SembrarUsuario
    director_id: uuid.UUID
    sesion_del_director: uuid.UUID

    def alta(self, documento: Documento, *, nombre_original: str | None = None) -> ArchivoSubido:
        """Alta por la interfaz publicada, a nombre del Director: declara el tamaño y la suma del contenido."""
        return dar_de_alta(
            self.aplicacion,
            self.motor,
            usuario_id=self.director_id,
            contenido=documento.contenido,
            nombre_original=documento.nombre if nombre_original is None else nombre_original,
            tipo_declarado=documento.tipo,
        )

    def disponible(
        self, documento: Documento, *, nombre_original: str | None = None
    ) -> ArchivoSubido:
        """Un archivo `DISPONIBLE` por el camino real: alta, `PUT` por la URL prefirmada y confirmación.

        Al volver, el espía del almacén queda en blanco: lo que cuenta es lo que hace la consulta.
        """
        archivo = self.alta(documento, nombre_original=nombre_original)
        subir_objeto(archivo)
        respuesta = confirmar_por_http(self.cliente, self.sesion_del_director, archivo.archivo_id)
        assert respuesta.status_code == 200, respuesta.text
        assert respuesta.json()["estado"] == "DISPONIBLE"
        self.almacen.reiniciar()
        return archivo

    def usuario_con_roles(self, correo: str, roles: tuple[str, ...]) -> tuple[uuid.UUID, uuid.UUID]:
        """Un usuario real con esos roles y su sesión abierta por HTTP: `(usuario_id, sesion_id)`."""
        usuario_id = self.sembrar_usuario(
            correo, CONTRASENA_DE_PRUEBA, roles=roles, nombre=NOMBRE_DEL_DIRECTOR
        )
        return usuario_id, iniciar_sesion(self.cliente, correo, CONTRASENA_DE_PRUEBA)

    def lector(self, rol: str) -> tuple[uuid.UUID, uuid.UUID]:
        """Un usuario con ese único rol, distinto de quien subió el archivo."""
        return self.usuario_con_roles(f"{rol.lower()}.consulta@cimenta.test", (rol,))

    def poner_estado(self, archivo: ArchivoSubido, estado: str) -> None:
        """Lleva la fila a `CADUCADO` o `ANULADO` por SQL: el barrido y la anulación llegan en otras filas."""
        with self.motor.begin() as conexion:
            if estado == "ANULADO":
                conexion.execute(
                    text(
                        "UPDATE archivo SET estado = 'ANULADO', anulado_por_id = :autor, "
                        "motivo_anulacion = :motivo, anulado_en = :cuando WHERE id = :id"
                    ),
                    {
                        "autor": self.director_id,
                        "motivo": "Se subió el archivo equivocado",
                        "cuando": self.reloj.ahora,
                        "id": archivo.archivo_id,
                    },
                )
            else:
                conexion.execute(
                    text("UPDATE archivo SET estado = :estado WHERE id = :id"),
                    {"estado": estado, "id": archivo.archivo_id},
                )

    def poner_tipo(self, archivo: ArchivoSubido, tipo_mime: str | None) -> None:
        """Deja el `tipo_mime` de la fila en ese valor por SQL, con el rol de aplicación.

        `ck_archivo_disponible_verificado` exige hash, tamaño y `confirmado_en` a un `DISPONIBLE`, pero no
        el tipo: la base admite un `DISPONIBLE` sin tipo o con uno fuera de la lista blanca.
        """
        with self.motor.begin() as conexion:
            conexion.execute(
                text("UPDATE archivo SET tipo_mime = :tipo WHERE id = :id"),
                {"tipo": tipo_mime, "id": archivo.archivo_id},
            )

    def fotografiar(self, archivo: ArchivoSubido) -> Fotografia:
        with self.motor.connect() as conexion:
            fila = (
                conexion.execute(
                    text("SELECT * FROM archivo WHERE id = :id"), {"id": archivo.archivo_id}
                )
                .mappings()
                .one()
            )
            sin_denegar = conexion.execute(
                text("SELECT count(*) FROM bitacora WHERE accion::text <> 'DENEGAR'")
            ).scalar_one()
            denegaciones = [
                dict(denegacion)
                for denegacion in conexion.execute(text(SQL_DENEGACIONES)).mappings().all()
            ]
        return Fotografia(
            fila=dict(fila),
            asientos_del_archivo=asientos_del_archivo(self.motor, archivo.archivo_id),
            bitacora_sin_denegar=sin_denegar,
            denegaciones=denegaciones,
        )

    def denegaciones(self) -> list[dict[str, Any]]:
        with self.motor.connect() as conexion:
            return [dict(f) for f in conexion.execute(text(SQL_DENEGACIONES)).mappings().all()]

    def total_de_la_bitacora(self) -> int:
        with self.motor.connect() as conexion:
            return conexion.execute(text("SELECT count(*) FROM bitacora")).scalar_one()

    def consultar(self, ruta: str, sesion_id: uuid.UUID | None) -> Respuesta:
        return leer(self.cliente, ruta, sesion_id)

    def descargar(self, url: str) -> httpx.Response:
        """`GET` real a la URL prefirmada, sin cookies ni cabeceras de la aplicación: es la credencial."""
        with httpx.Client(timeout=LIMITE_DE_LECTURA_SEGUNDOS) as cliente:
            return cliente.get(url)


@pytest.fixture
def escena(
    almacen: AlmacenS3,
    cliente_s3: S3Client,
    bucket_de_pruebas: str,
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    registro_tecnico: io.StringIO,
) -> Iterator[Escena]:
    espia = AlmacenEspia(almacen)
    aplicacion = crear_aplicacion_de_archivos(
        almacen=espia.como_almacen(),
        motor=motor_aplicacion,
        reloj=reloj_de_prueba,
        destino_registro=registro_tecnico,
    )
    director_id = sembrar_director(sembrar_usuario)
    with cliente_https(aplicacion) as cliente:
        yield Escena(
            cliente=cliente,
            aplicacion=aplicacion,
            motor=motor_aplicacion,
            reloj=reloj_de_prueba,
            almacen=espia,
            s3=cliente_s3,
            bucket=bucket_de_pruebas,
            origen_del_almacen=str(cliente_s3.meta.endpoint_url),
            sembrar_usuario=sembrar_usuario,
            director_id=director_id,
            sesion_del_director=abrir_sesion_del_director(cliente),
        )


# --------------------------------------------------------------------------- comprobaciones comunes


def _exigir_error(
    respuesta: Respuesta, *, estado: int, esperado: dict[str, Any], esquema: str
) -> None:
    """El contrato de error completo, con la diferencia a la vista cuando falla.

    `exigir_error` vive en un módulo que pytest no reescribe y su `assert` falla sin mensaje; aquí se
    compara antes el código y el cuerpo (sin la correlación) para que un rojo diga qué difiere, y después
    se delega en `exigir_error` para la correlación, el esquema del borrador y la ausencia de trazas.
    """
    assert respuesta.status_code == estado, respuesta.text
    cuerpo = {
        clave: valor for clave, valor in respuesta.json().items() if clave != "correlacion_id"
    }
    assert cuerpo == esperado
    exigir_error(respuesta, estado=estado, esperado=esperado, esquema=esquema)


def _exigir_conflicto(
    respuesta: Respuesta, *, codigo: str, mensaje: str, detalle: dict[str, Any]
) -> None:
    """El contrato de un `409 CONFLICTO` completo: `tipo`, `codigo`, `mensaje`, `detalle`, `acciones` vacías."""
    _exigir_error(
        respuesta,
        estado=409,
        esperado={
            "tipo": "CONFLICTO",
            "codigo": codigo,
            "mensaje": mensaje,
            "detalle": detalle,
            "acciones": [],
        },
        esquema="ErrorConflictoEstado",
    )


def _exigir_permiso(respuesta: Respuesta) -> None:
    """El contrato de un `403 PERMISO` por rol: cuerpo exacto, sin `detalle` y sin datos del recurso."""
    _exigir_error(
        respuesta,
        estado=403,
        esperado={
            "tipo": "PERMISO",
            "motivo": "ROL_INSUFICIENTE",
            "mensaje": MENSAJE_ROL_INSUFICIENTE,
            "roles_requeridos": ROLES_DE_CONSULTA,
        },
        esquema="ErrorPermiso",
    )


def _exigir_no_encontrado(respuesta: Respuesta) -> None:
    _exigir_error(
        respuesta,
        estado=404,
        esperado={"tipo": "NO_ENCONTRADO", "mensaje": MENSAJE_NO_EXISTE, "recurso": "archivo"},
        esquema="ErrorNoEncontrado",
    )


def _sin_datos_ni_url(respuesta: Respuesta, archivo: ArchivoSubido) -> None:
    """Ni una cifra, ni un identificador, ni una dirección del almacén en el cuerpo de un rechazo."""
    cuerpo = respuesta.json()
    assert "url" not in cuerpo
    assert "detalle" not in cuerpo
    for dato in (
        str(archivo.archivo_id),
        str(archivo.obra_id),
        archivo.nombre_original,
        archivo.hash_sha256,
        archivo.clave,
        "X-Amz",
        "http",
    ):
        assert dato not in respuesta.text, f"El rechazo no puede revelar {dato!r}"


def _denegacion(
    escena: Escena, *, usuario_id: uuid.UUID, ruta: str, roles_requeridos: list[str]
) -> dict[str, Any]:
    """El asiento `DENEGAR` que debe quedar, a nombre de quien llamó (modelo de datos §10, C-1 enmendado)."""
    return {
        "usuario_id": usuario_id,
        "ocurrido_en": escena.reloj.ahora,
        "motivo": "ROL_INSUFICIENTE",
        "regla_negocio": None,
        "entidad_tipo": "usuario",
        "entidad_id": usuario_id,
        "obra_id": None,
        "datos_antes_es_nulo": True,
        "datos_despues": {"metodo": "GET", "ruta": ruta, "roles_requeridos": roles_requeridos},
    }


def _instante(texto: str) -> datetime:
    instante = datetime.fromisoformat(texto)
    assert instante.tzinfo is not None, f"La fecha {texto!r} no lleva zona"
    return instante


def _consulta_de(url: str) -> dict[str, str]:
    return dict(parse_qsl(urlsplit(url).query, keep_blank_values=True))


def _con_consulta_cambiada(url: str, cambios: dict[str, str | None]) -> str:
    """La misma URL con parámetros de consulta cambiados (`None` los quita) y la firma intacta."""
    partes = urlsplit(url)
    consulta = {**_consulta_de(url), **cambios}
    nueva = urlencode({k: v for k, v in consulta.items() if v is not None})
    return partes._replace(query=nueva).geturl()


def _emitir(escena: Escena, archivo: ArchivoSubido, sesion_id: uuid.UUID) -> dict[str, Any]:
    """`GET …/descarga` con un lector autorizado: el cuerpo de la `UrlDescarga`, ya comprobado `200`."""
    respuesta = escena.consultar(ruta_de_descarga(archivo.archivo_id), sesion_id)
    assert respuesta.status_code == 200, respuesta.text
    cuerpo: dict[str, Any] = respuesta.json()
    return cuerpo


# --------------------------------------------------------------------------- TC-31


@pytest.mark.parametrize("rol", AMBOS_ROLES)
def test_tkt059_ca08_descargar_un_pdf(escena: Escena, rol: str) -> None:
    """TC-31 · CA-8 esc. 1 · RNF-06 · ADR-016 — un PDF `DISPONIBLE` se descarga por una URL prefirmada: `200` y `attachment`.

    Para `DIRECCION_GENERAL` y `DIRECTOR_PROYECTOS`, que no son quien subió el archivo. El cuerpo valida
    contra `UrlDescarga` del borrador y tiene exactamente sus propiedades. La `url` empieza por el origen
    del almacén (no por el de la aplicación), vive cinco minutos (`expira_en == reloj + 5 min`, con zona;
    `X-Amz-Expires=300`) y se firmó una sola vez con el tipo, el nombre y la disposición de la fila. Un
    `GET` real a esa URL, sin cookies, responde `200` con los bytes del PDF, `Content-Type:
    application/pdf` y un `Content-Disposition` que empieza por `attachment;` y lleva el nombre.
    """
    archivo = escena.disponible(PDF)
    _, sesion = escena.lector(rol)

    respuesta = escena.consultar(ruta_de_descarga(archivo.archivo_id), sesion)

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.headers["content-type"].startswith("application/json")
    cuerpo = respuesta.json()
    validar_contra("UrlDescarga", cuerpo)
    assert set(cuerpo) == set(borrador()["components"]["schemas"]["UrlDescarga"]["properties"])
    assert cuerpo["url"].startswith(escena.origen_del_almacen + "/")
    assert cuerpo["tipo_mime"] == TIPO_PDF
    assert cuerpo["nombre_original"] == PDF.nombre
    assert cuerpo["disposicion"] == "attachment"
    assert _instante(cuerpo["expira_en"]) == escena.reloj.ahora + VIDA_DE_LA_URL_DE_LECTURA
    assert _consulta_de(cuerpo["url"])["X-Amz-Expires"] == "300"
    assert escena.almacen.urls_de_lectura == [
        {
            "clave": archivo.clave,
            "vida": VIDA_DE_LA_URL_DE_LECTURA,
            "tipo_mime": TIPO_PDF,
            "nombre_original": PDF.nombre,
            "disposicion": "attachment",
        }
    ]

    contenido = escena.descargar(cuerpo["url"])

    assert contenido.status_code == 200, contenido.text
    assert contenido.content == PDF.contenido
    assert contenido.headers["content-type"] == TIPO_PDF
    disposicion = contenido.headers["content-disposition"]
    assert disposicion.startswith("attachment;")
    assert f'filename="{PDF.nombre}"' in disposicion
    assert f"filename*=UTF-8''{quote(PDF.nombre, safe='')}" in disposicion


# --------------------------------------------------------------------------- TC-32


def test_tkt059_ca08_una_imagen_en_linea(escena: Escena) -> None:
    """TC-32 · CA-8 esc. 2 · ADR-016 regla 3 — un JPEG `DISPONIBLE` se sirve `inline`: `disposicion` y cabecera lo dicen.

    Imagen y video son los únicos tipos que se muestran en la página; todo lo demás se descarga. El cuerpo
    valida contra `UrlDescarga` con `disposicion` `inline`, y el `GET` real a la URL responde `200` con
    `Content-Type: image/jpeg` y un `Content-Disposition` que empieza por `inline;`.
    """
    archivo = escena.disponible(JPEG)
    _, sesion = escena.lector("DIRECCION_GENERAL")

    respuesta = escena.consultar(ruta_de_descarga(archivo.archivo_id), sesion)

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    validar_contra("UrlDescarga", cuerpo)
    assert cuerpo["tipo_mime"] == TIPO_JPEG
    assert cuerpo["disposicion"] == "inline"
    assert cuerpo["url"].startswith(escena.origen_del_almacen + "/")
    assert _instante(cuerpo["expira_en"]) == escena.reloj.ahora + VIDA_DE_LA_URL_DE_LECTURA

    contenido = escena.descargar(cuerpo["url"])

    assert contenido.status_code == 200, contenido.text
    assert contenido.content == JPEG.contenido
    assert contenido.headers["content-type"] == TIPO_JPEG
    disposicion = contenido.headers["content-disposition"]
    assert disposicion.startswith("inline;")
    assert f'filename="{JPEG.nombre}"' in disposicion


# --------------------------------------------------------------------------- TC-34


@pytest.mark.parametrize("rol", AMBOS_ROLES)
def test_tkt059_ca08_metadatos(escena: Escena, rol: str) -> None:
    """TC-34 · CA-8 esc. 4 · ADR-016 — los metadatos de un archivo `DISPONIBLE`: `200`, valida contra `Archivo` y no lleva `clave_objeto`.

    Para los dos roles de lectura, ninguno de los cuales subió el archivo. Las claves del cuerpo son
    exactamente las propiedades del esquema del borrador; nada de la clave del objeto, del bucket ni de una
    dirección del almacén. Se lee solo de la base: no se llama al almacén.
    """
    archivo = escena.disponible(XLSX)
    _, sesion = escena.lector(rol)

    respuesta = escena.consultar(ruta_de_metadatos(archivo.archivo_id), sesion)

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.headers["content-type"].startswith("application/json")
    cuerpo = respuesta.json()
    validar_contra("Archivo", cuerpo)
    assert set(cuerpo) == set(borrador()["components"]["schemas"]["Archivo"]["properties"])
    assert "clave_objeto" not in cuerpo
    for dato in (archivo.clave, escena.bucket, escena.origen_del_almacen):
        assert dato not in respuesta.text
    assert {clave: valor for clave, valor in cuerpo.items() if not clave.endswith("_en")} == {
        "id": str(archivo.archivo_id),
        "obra_id": str(archivo.obra_id),
        "referencia_tipo": "IMPORTACION",
        "referencia_id": str(archivo.referencia_id),
        "estado": "DISPONIBLE",
        "nombre_original": XLSX.nombre,
        "tipo_mime": TIPO_XLSX,
        "tamano_bytes": len(XLSX.contenido),
        "hash_sha256": archivo.hash_sha256,
        "subido_por": {"id": str(escena.director_id), "nombre": NOMBRE_DEL_DIRECTOR},
    }
    assert _instante(cuerpo["creado_en"]) == escena.reloj.ahora
    assert _instante(cuerpo["confirmado_en"]) == escena.reloj.ahora
    assert escena.almacen.llamadas_metadatos == []
    assert escena.almacen.urls_de_lectura == []


@pytest.mark.parametrize("rol", AMBOS_ROLES)
def test_tkt059_ca08_metadatos_de_un_caducado(escena: Escena, rol: str) -> None:
    """TC-34 · CA-8 esc. 4 — un archivo `CADUCADO` también se consulta: sale con ese estado y valida contra `Archivo`.

    Los metadatos no dependen de que el archivo se pueda descargar. La fila no cambia y no se asienta nada.
    """
    archivo = escena.alta(PDF)
    escena.poner_estado(archivo, "CADUCADO")
    _, sesion = escena.lector(rol)
    antes = escena.fotografiar(archivo)

    respuesta = escena.consultar(ruta_de_metadatos(archivo.archivo_id), sesion)

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    validar_contra("Archivo", cuerpo)
    assert set(cuerpo) == set(borrador()["components"]["schemas"]["Archivo"]["properties"])
    assert cuerpo["estado"] == "CADUCADO"
    assert cuerpo["id"] == str(archivo.archivo_id)
    assert cuerpo["tipo_mime"] is None
    assert cuerpo["confirmado_en"] is None
    assert "clave_objeto" not in cuerpo
    assert escena.fotografiar(archivo) == antes


@pytest.mark.parametrize("estado", ["PENDIENTE", "ANULADO"])
def test_tkt059_ca08_metadatos_de_un_pendiente_o_anulado(escena: Escena, estado: str) -> None:
    """TC-34 (extra, asumido) · CA-8 esc. 4 — los metadatos no se niegan por estado: `PENDIENTE` y `ANULADO` salen con el suyo.

    El diseño solo restringe la descarga por estado; `obtener_archivo` devuelve la fila tal cual. La
    asunción queda anotada en el informe de la fila 14.
    """
    archivo = escena.alta(PDF)
    if estado != "PENDIENTE":
        escena.poner_estado(archivo, estado)
    _, sesion = escena.lector("DIRECTOR_PROYECTOS")

    respuesta = escena.consultar(ruta_de_metadatos(archivo.archivo_id), sesion)

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    validar_contra("Archivo", cuerpo)
    assert cuerpo["estado"] == estado
    assert "clave_objeto" not in cuerpo


# --------------------------------------------------------------------------- TC-35


@pytest.mark.parametrize("rol", AMBOS_ROLES)
@pytest.mark.parametrize(
    ("estado", "codigo", "mensaje"),
    [
        pytest.param("PENDIENTE", "ARCHIVO_NO_DISPONIBLE", MENSAJE_NO_DISPONIBLE, id="pendiente"),
        pytest.param("ANULADO", "ARCHIVO_NO_DISPONIBLE", MENSAJE_NO_DISPONIBLE, id="anulado"),
        pytest.param("CADUCADO", "ARCHIVO_CADUCADO", MENSAJE_CADUCADO_AL_DESCARGAR, id="caducado"),
    ],
)
def test_tkt059_ca09_descarga_no_disponible(
    escena: Escena, rol: str, estado: str, codigo: str, mensaje: str
) -> None:
    """TC-35 · CA-9 esc. 1 y 2 · ADR-016 — una descarga que todavía no existe o ya no existe es un `409` `CONFLICTO`, no una URL.

    `PENDIENTE` (nadie confirmó) y `ANULADO` → `ARCHIVO_NO_DISPONIBLE`; `CADUCADO` → `ARCHIVO_CADUCADO`. El
    cuerpo es exacto: `tipo`, `codigo`, `mensaje` literal del diseño, `detalle` con solo `archivo_id` y
    `estado_archivo`, y `acciones` vacías; ninguna `url`. El almacén no firma nada y no se le consulta, y
    la fila y la bitácora quedan como estaban (el `409` no es un `DENEGAR`).
    """
    archivo = escena.alta(PDF)
    if estado != "PENDIENTE":
        escena.poner_estado(archivo, estado)
    _, sesion = escena.lector(rol)
    antes = escena.fotografiar(archivo)
    assert antes.fila["estado"] == estado

    respuesta = escena.consultar(ruta_de_descarga(archivo.archivo_id), sesion)

    _exigir_conflicto(
        respuesta,
        codigo=codigo,
        mensaje=mensaje,
        detalle={"archivo_id": str(archivo.archivo_id), "estado_archivo": estado},
    )
    cuerpo = respuesta.json()
    assert set(cuerpo["detalle"]) == {"archivo_id", "estado_archivo"}
    assert "url" not in cuerpo
    assert "X-Amz" not in respuesta.text
    assert escena.almacen.urls_de_lectura == []
    assert escena.almacen.llamadas_metadatos == []
    assert escena.fotografiar(archivo) == antes


# --------------------------------------------------------------------------- TC-36


@pytest.mark.parametrize("ruta_de", AMBAS_RUTAS)
@pytest.mark.parametrize("rol", ROLES_SIN_PERMISO)
def test_tkt059_ca09_sin_rol(escena: Escena, rol: str, ruta_de: Callable[[uuid.UUID], str]) -> None:
    """TC-36 · CA-9 esc. 3 · RN-04 — sin `DIRECCION_GENERAL` ni `DIRECTOR_PROYECTOS`: `403` `PERMISO` `ROL_INSUFICIENTE`, sin datos ni URL y con un `DENEGAR`.

    Los cuatro roles restantes en las dos rutas `GET`, sobre un archivo `DISPONIBLE` que sí se podría
    descargar. Cuerpo exacto con `roles_requeridos` igual al `x-roles` del borrador, sin `detalle`, sin
    identificadores, sin nombre ni hash y sin `url`. El asiento `DENEGAR` es de quien llamó, con
    `ROL_INSUFICIENTE`, `GET` y la ruta; la fila, sus asientos y el resto de la bitácora no cambian, y el
    almacén ni se consulta ni firma nada.
    """
    archivo = escena.disponible(PDF)
    usuario_id, sesion = escena.lector(rol)
    antes = escena.fotografiar(archivo)
    ruta = ruta_de(archivo.archivo_id)

    respuesta = escena.consultar(ruta, sesion)

    _exigir_permiso(respuesta)
    _sin_datos_ni_url(respuesta, archivo)
    despues = escena.fotografiar(archivo)
    assert despues.denegaciones == [
        *antes.denegaciones,
        _denegacion(escena, usuario_id=usuario_id, ruta=ruta, roles_requeridos=ROLES_DE_CONSULTA),
    ]
    assert replace(despues, denegaciones=antes.denegaciones) == antes
    assert escena.almacen.urls_de_lectura == []
    assert escena.almacen.llamadas_metadatos == []


@pytest.mark.parametrize("rol", ROLES_SIN_PERMISO)
def test_tkt059_ca09_sin_rol_no_se_firma_ninguna_url(escena: Escena, rol: str) -> None:
    """TC-36 · CA-9 esc. 3 · ADR-016 — el rol se comprueba **al emitir**: con la sesión de un rol sin permiso no se firma ninguna URL.

    El espía de `url_lectura` no registra llamadas tras el `403`. Control: con el mismo archivo, un rol
    autorizado sí provoca exactamente una llamada, así que el espía funciona y un espía vacío significa que
    no se firmó. Mutante `M-12`: si `exigir_rol` admitiera también a `COMPRAS`, el `403` desaparecería y el
    espía registraría una URL.
    """
    archivo = escena.disponible(PDF)
    _, sesion_sin_permiso = escena.lector(rol)
    _, sesion_autorizada = escena.lector("DIRECCION_GENERAL")

    rechazada = escena.consultar(ruta_de_descarga(archivo.archivo_id), sesion_sin_permiso)

    assert rechazada.status_code == 403, rechazada.text
    assert escena.almacen.urls_de_lectura == [], "Un rol sin permiso no debe provocar ninguna firma"

    emitida = escena.consultar(ruta_de_descarga(archivo.archivo_id), sesion_autorizada)

    assert emitida.status_code == 200, emitida.text
    assert len(escena.almacen.urls_de_lectura) == 1


@pytest.mark.parametrize("ruta_de", AMBAS_RUTAS)
def test_tkt059_ca09_el_rol_se_comprueba_antes_que_la_existencia(
    escena: Escena, ruta_de: Callable[[uuid.UUID], str]
) -> None:
    """TC-36 · CA-9 esc. 3 · conv-seguridad — quien no tiene rol recibe `403` aunque el archivo no exista: no se averigua qué existe."""
    usuario_id, sesion = escena.lector("RESIDENTE")
    inexistente = uuid.uuid4()
    ruta = ruta_de(inexistente)
    denegaciones_antes = escena.denegaciones()

    respuesta = escena.consultar(ruta, sesion)

    _exigir_permiso(respuesta)
    assert str(inexistente) not in respuesta.text
    assert escena.denegaciones() == [
        *denegaciones_antes,
        _denegacion(escena, usuario_id=usuario_id, ruta=ruta, roles_requeridos=ROLES_DE_CONSULTA),
    ]
    assert escena.almacen.urls_de_lectura == []


@pytest.mark.parametrize("ruta_de", AMBAS_RUTAS)
@pytest.mark.parametrize("rol", AMBOS_ROLES)
def test_tkt059_ca09_archivo_inexistente(
    escena: Escena, rol: str, ruta_de: Callable[[uuid.UUID], str]
) -> None:
    """TC-36 · CA-9 esc. 3 — un identificador que no existe: `404` `NO_ENCONTRADO` con `recurso` `archivo`.

    Cuerpo exacto con el mensaje del diseño, en las dos rutas y para los dos roles. No se asienta nada, el
    almacén no se consulta y no se firma ninguna URL.
    """
    _, sesion = escena.lector(rol)
    antes = escena.total_de_la_bitacora()

    respuesta = escena.consultar(ruta_de(uuid.uuid4()), sesion)

    _exigir_no_encontrado(respuesta)
    assert escena.total_de_la_bitacora() == antes
    assert escena.almacen.urls_de_lectura == []
    assert escena.almacen.llamadas_metadatos == []


@pytest.mark.parametrize("ruta_de", AMBAS_RUTAS)
@pytest.mark.parametrize("sesion", ["sin_cookie", "sesion_inexistente"])
def test_tkt059_ca09_sin_sesion(
    escena: Escena, sesion: str, ruta_de: Callable[[uuid.UUID], str]
) -> None:
    """TC-36 · CA-9 esc. 3 · RNF-13 — sin sesión (o con una que no existe): `401` `SESION` `SIN_SESION`.

    El cuerpo no revela nada del archivo, que existe y está `DISPONIBLE`; no se firma ninguna URL y la fila
    y la bitácora quedan como estaban (un rechazo anónimo no se asienta).
    """
    archivo = escena.disponible(PDF)
    antes = escena.fotografiar(archivo)

    respuesta = escena.consultar(
        ruta_de(archivo.archivo_id), uuid.uuid4() if sesion == "sesion_inexistente" else None
    )

    _exigir_error(
        respuesta,
        estado=401,
        esperado={"tipo": "SESION", "motivo": "SIN_SESION", "mensaje": MENSAJE_SIN_SESION},
        esquema="ErrorSesion",
    )
    _sin_datos_ni_url(respuesta, archivo)
    assert escena.fotografiar(archivo) == antes
    assert escena.almacen.urls_de_lectura == []


# --------------------------------------------------------------------------- defensa de O-4


@pytest.mark.parametrize("documento", DOCUMENTOS)
def test_tkt059_ca08_la_url_lleva_el_tipo_y_la_disposicion_firmados(
    escena: Escena, documento: Documento
) -> None:
    """O-4 · ADR-016 regla 3 — la URL fija `response-content-type` y `response-content-disposition`, y ambos van firmados.

    Los parámetros de la consulta valen el tipo de la fila y la disposición de la lista blanca (con el
    nombre). Como forman parte de la firma, nadie puede cambiarlos para servir el archivo `inline` ni con
    otro tipo: cambiar el tipo, cambiar la disposición o quitar cualquiera de los dos responde `403` del
    almacén. Control: la misma URL, reconstruida sin cambios, sirve el archivo con `200`.
    """
    archivo = escena.disponible(documento)
    _, sesion = escena.lector("DIRECTOR_PROYECTOS")
    url = _emitir(escena, archivo, sesion)["url"]

    consulta = _consulta_de(url)

    assert consulta["response-content-type"] == documento.tipo
    assert consulta["response-content-disposition"].startswith(f"{documento.disposicion};")
    assert documento.nombre in consulta["response-content-disposition"]
    assert consulta["X-Amz-Signature"]
    control = escena.descargar(_con_consulta_cambiada(url, {}))
    assert control.status_code == 200, control.text
    manipulaciones: dict[str, dict[str, str | None]] = {
        "otro_tipo": {"response-content-type": "text/html"},
        "disposicion_en_linea": {"response-content-disposition": "inline"},
        "sin_tipo": {"response-content-type": None},
        "sin_disposicion": {"response-content-disposition": None},
    }
    for nombre, cambios in manipulaciones.items():
        manipulada = escena.descargar(_con_consulta_cambiada(url, cambios))
        assert manipulada.status_code == 403, (
            f"{nombre}: {manipulada.status_code} {manipulada.text}"
        )


@pytest.mark.parametrize("documento", [XML, XLSX], ids=["xml", "xlsx"])
@pytest.mark.parametrize("rol", AMBOS_ROLES)
def test_tkt059_ca08_xml_y_xlsx_siempre_se_descargan(
    escena: Escena, rol: str, documento: Documento
) -> None:
    """O-4 · ADR-016 regla 3 — un XML y un `.xlsx` se sirven siempre como `attachment`, nunca `inline`.

    Un XML mostrado en la página ejecuta lo que lleve; ninguno de los dos se previsualiza. La `UrlDescarga`
    dice `attachment` y el `GET` real a la URL devuelve `Content-Disposition` con `attachment;` y ninguna
    señal de `inline`, con el tipo de la fila y los mismos bytes. Para los dos roles de lectura.
    """
    archivo = escena.disponible(documento)
    _, sesion = escena.lector(rol)

    cuerpo = _emitir(escena, archivo, sesion)

    assert cuerpo["disposicion"] == "attachment"
    assert cuerpo["tipo_mime"] == documento.tipo
    assert escena.almacen.urls_de_lectura[-1]["disposicion"] == "attachment"
    contenido = escena.descargar(cuerpo["url"])
    assert contenido.status_code == 200, contenido.text
    assert contenido.content == documento.contenido
    assert contenido.headers["content-type"] == documento.tipo
    disposicion = contenido.headers["content-disposition"]
    assert disposicion.startswith("attachment;")
    assert "inline" not in disposicion.lower()


@pytest.mark.parametrize("documento", DOCUMENTOS)
def test_tkt059_ca08_el_tipo_de_la_respuesta_es_el_de_la_fila(
    escena: Escena, documento: Documento
) -> None:
    """O-4 · ADR-016 regla 3 — el `Content-Type` que entrega el almacén es el de la fila, aunque el objeto diga otro.

    Tras confirmar, otro `PUT` con un cliente directo sobrescribe el objeto con `Content-Type: text/html`
    (el tipo que un navegador ejecutaría). Se comprueba primero que el objeto quedó con ese tipo y después
    que el `GET` por la URL emitida responde con el tipo de la fila: `response-content-type` manda, y el
    nombre y la disposición siguen siendo los de la fila.
    """
    archivo = escena.disponible(documento)
    _, sesion = escena.lector("DIRECCION_GENERAL")
    escena.s3.put_object(
        Bucket=escena.bucket, Key=archivo.clave, Body=documento.contenido, ContentType="text/html"
    )
    assert escena.s3.head_object(Bucket=escena.bucket, Key=archivo.clave)["ContentType"] == (
        "text/html"
    )

    cuerpo = _emitir(escena, archivo, sesion)
    contenido = escena.descargar(cuerpo["url"])

    assert contenido.status_code == 200, contenido.text
    assert cuerpo["tipo_mime"] == documento.tipo
    assert contenido.headers["content-type"] == documento.tipo
    assert contenido.headers["content-disposition"].startswith(f"{documento.disposicion};")


@pytest.mark.parametrize(
    ("nombre", "ascii_esperado"),
    [
        pytest.param("Cotización ñandú.pdf", "Cotizaci_n _and_.pdf", id="no_ascii"),
        pytest.param('Plano "final".pdf', "Plano _final_.pdf", id="comillas"),
        pytest.param("informe\r\nSet-Cookie: x=1.pdf", "informe__Set-Cookie: x=1.pdf", id="crlf"),
    ],
)
def test_tkt059_ca08_el_nombre_no_rompe_la_cabecera(
    escena: Escena, nombre: str, ascii_esperado: str
) -> None:
    """O-4 · ADR-016 regla 3 · RFC 6266 — el nombre del archivo no puede romper ni inyectar la cabecera `Content-Disposition`.

    El alta admite nombres con acentos, comillas y saltos de línea. La parte `filename=` queda en ASCII
    visible con `_` en lugar de cada carácter peligroso, y `filename*=UTF-8''` lleva el nombre completo
    codificado. La respuesta del almacén no trae una cabecera inyectada (`Set-Cookie`) y la `UrlDescarga`
    conserva el nombre original tal cual.
    """
    documento = replace(PDF, nombre=nombre)
    archivo = escena.disponible(documento)
    _, sesion = escena.lector("DIRECTOR_PROYECTOS")

    cuerpo = _emitir(escena, archivo, sesion)
    contenido = escena.descargar(cuerpo["url"])

    assert cuerpo["nombre_original"] == nombre
    assert contenido.status_code == 200, contenido.text
    disposicion = contenido.headers["content-disposition"]
    assert disposicion.startswith("attachment;")
    assert f'filename="{ascii_esperado}"' in disposicion
    assert f"filename*=UTF-8''{quote(nombre, safe='')}" in disposicion
    assert "set-cookie" not in contenido.headers
    assert "\r" not in disposicion
    assert "\n" not in disposicion


# --------------------------------------------------------------------------- invariante defensivo (F001)


@pytest.mark.parametrize("rol", AMBOS_ROLES)
@pytest.mark.parametrize(
    "tipo_en_la_fila",
    [
        pytest.param(None, id="sin_tipo"),
        pytest.param("image/svg+xml", id="svg_fuera_de_la_lista_blanca"),
    ],
)
def test_tkt059_ca08_un_disponible_sin_tipo_admitido_es_500_y_no_firma_url(
    escena: Escena, registro_tecnico: io.StringIO, rol: str, tipo_en_la_fila: str | None
) -> None:
    """F001 · CA-8 · ADR-016 regla 3 — un `DISPONIBLE` cuyo tipo falta o salió de la lista blanca no se firma: `500` del contrato.

    La base lo admite (`ck_archivo_disponible_verificado` no exige `tipo_mime`) y `disposicion_de` no tiene
    disposición para `image/svg+xml`: el caso de uso lo trata como un invariante roto (`RuntimeError`), no
    como un `409`, y no sirve el archivo con un tipo que la lista blanca no admite. El `500` es el del
    contrato (solo `mensaje` y `correlacion_id`, sin traza ni nombre de excepción); el espía de
    `url_lectura` no registra llamadas y la fila y la bitácora quedan como estaban. Control: el mismo
    archivo con su tipo restituido sí obtiene una URL (el espía registra una).
    """
    archivo = escena.disponible(PDF)
    escena.poner_tipo(archivo, tipo_en_la_fila)
    _, sesion = escena.lector(rol)
    antes = escena.fotografiar(archivo)
    assert antes.fila["estado"] == "DISPONIBLE"
    assert antes.fila["tipo_mime"] == tipo_en_la_fila

    respuesta = escena.consultar(ruta_de_descarga(archivo.archivo_id), sesion)

    assert respuesta.status_code == 500, respuesta.text
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"mensaje", "correlacion_id"}
    assert cuerpo["correlacion_id"] == respuesta.headers[CABECERA_CORRELACION]
    for pista in (
        "RuntimeError",
        "invariante",
        "siempre tiene",
        "Traceback",
        "cimenta.",
        "sqlalchemy",
        "X-Amz",
        "url",
        str(archivo.archivo_id),
        archivo.clave,
    ):
        assert pista not in respuesta.text, f"El 500 no puede revelar {pista!r}"
    assert escena.almacen.urls_de_lectura == []
    assert escena.fotografiar(archivo) == antes
    # El registro técnico sí dice qué falló, con el tipo y los marcos pero sin `str(exc)`: que sea el
    # invariante defensivo (`RuntimeError`) y no otro fallo de paso (un `TypeError` al clasificar `None`).
    assert "RuntimeError" in registro_tecnico.getvalue()
    assert "emitir_url_descarga" in registro_tecnico.getvalue()

    escena.poner_tipo(archivo, TIPO_PDF)
    control = escena.consultar(ruta_de_descarga(archivo.archivo_id), sesion)

    assert control.status_code == 200, control.text
    assert len(escena.almacen.urls_de_lectura) == 1
