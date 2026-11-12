"""Rechazos de la confirmación de un archivo por la API (TKT-059, fila 12b): TC-19, TC-20, TC-22 a TC-24 y TC-26 a TC-30.

`POST /api/v1/archivos/{archivo_id}/confirmacion` comprueba el objeto **realmente almacenado** y a quien
confirma. Cada rechazo se prueba con el contrato de error completo —`tipo`, `codigo` o `motivo`, `mensaje`
literal del diseño, `detalle` con sus valores, `acciones` y `correlacion_id`— y después con una fotografía
de lo que no debió cambiar: la fila de `archivo` entera, los asientos del archivo, el resto de la bitácora,
las denegaciones y el `Content-Type` del objeto en el almacén.

PostgreSQL y MinIO reales con testcontainers: el esquema sale de `alembic upgrade head`, las escrituras
van con el rol de aplicación, y los objetos se siembran con un cliente `boto3` directo o con un `PUT`
real por la URL prefirmada. Las altas y las siembras de `PENDIENTE` se hacen **dentro** del bloque
`with TestClient(...)` que abre la fixture `escena` (preámbulo del plan de pruebas). Ningún `sleep`.

Estado de esta fila: los rechazos ya los puso en verde la fila 12a. Estas pruebas nacen en verde, y por
eso su rojo se demuestra con **mutantes temporales** sobre el código de producción (diseño, fila 12b): el
registro literal de cada uno está en `sdd/tickets/tkt-059/rojo/fila-12b.txt`.

Los tests cuyo nombre empieza por `test_hdu001_esc25_` y `test_hdu001_esc26_` son los escenarios 25 y 26 de
HDU-001; el 24 es de TKT-018. Hay un caso extra, `ESTADO_NO_PERMITE_OPERACION` (regla `P-10`), que el plan
no lista.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import time
import uuid
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest
from botocore.exceptions import ClientError
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from herramientas.soporte_tkt017_api import (
    CABECERA_CORRELACION,
    CONTRASENA_DE_PRUEBA,
    NOMBRE_DEL_DIRECTOR,
    SIN_PAR_VALIDO,
    TOKEN_CSRF,
    cabeceras_de,
    exigir_error,
    iniciar_sesion,
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
    ruta_de_confirmacion,
    sembrar_director,
    subir_objeto,
)

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta.
    from conftest import RelojDePrueba, SembrarUsuario
    from mypy_boto3_s3 import S3Client

    from cimenta.archivos.infraestructura.almacen_s3 import AlmacenS3

# --------------------------------------------------------------------------- literales del diseño

MENSAJE_NO_SUBIDO = "El archivo no llegó al almacén. Vuelve a cargarlo antes de confirmar."
MENSAJE_TAMANO = (
    "El archivo almacenado no tiene el tamaño que se declaró al iniciar la subida. "
    "Vuelve a cargar el archivo."
)
MENSAJE_HASH = (
    "El archivo almacenado no coincide con el que se declaró al iniciar la subida. "
    "Vuelve a cargar el archivo."
)
MENSAJE_TIPO = "El tipo del archivo, leído de su contenido, no está permitido."
MENSAJE_CADUCADO = "La subida del archivo caducó. Vuelve a cargar el archivo."
MENSAJE_ANULADO = "El archivo está anulado y no se confirma."
MENSAJE_NO_SOLICITANTE = "Solo quien subió el archivo puede confirmarlo."
MENSAJE_NO_EXISTE = "El archivo no existe."
MENSAJE_ROL_INSUFICIENTE = "Tu rol no permite esta operación."
MENSAJE_ORIGEN_NO_VERIFICADO = (
    "No se pudo comprobar que la petición venga de CIMENTA. Recarga la página e inténtalo de nuevo."
)
MENSAJE_SIN_SESION = "No hay una sesión iniciada."

# La lista blanca, en el orden de la tabla del diseño. Se escribe aquí a propósito: es el oráculo.
TIPOS_ADMITIDOS = [
    "image/jpeg",
    "image/png",
    "image/heic",
    "image/webp",
    "video/mp4",
    "application/pdf",
    "application/xml",
    TIPO_XLSX,
]
ROL_DE_CONFIRMACION = "DIRECTOR_PROYECTOS"
ROLES_SIN_PERMISO = ["DIRECCION_GENERAL", "COMPRAS", "RESIDENTE", "ALMACEN", "ADMINISTRACION"]
UMBRAL_DE_PENDIENTE = timedelta(hours=24)
LIMITE_DE_LA_EXPANSION_SEGUNDOS = 5.0

PARTE_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"
PARTE_XLSM = "application/vnd.ms-excel.sheet.macroEnabled.main+xml"
PARTE_HOJA = "application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"

CORREO_OTRO_DIRECTOR = "otro.director.archivos@cimenta.test"

SQL_DENEGACIONES = (
    "SELECT usuario_id, ocurrido_en, motivo, regla_negocio, entidad_tipo, entidad_id, obra_id, "
    "datos_antes IS NULL AS datos_antes_es_nulo, datos_despues "
    "FROM bitacora WHERE accion::text = 'DENEGAR' ORDER BY ocurrido_en, id"
)


# --------------------------------------------------------------------------- contenidos hostiles


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


def _zip(entradas: dict[str, bytes]) -> bytes:
    memoria = io.BytesIO()
    with zipfile.ZipFile(memoria, "w") as archivo_zip:
        for nombre, datos in entradas.items():
            archivo_zip.writestr(nombre, datos, compress_type=zipfile.ZIP_DEFLATED)
    return memoria.getvalue()


def _ejecutable_mz() -> bytes:
    return (
        b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00" + b"\x00" * 64 + b"PE\x00\x00"
    )


def _svg() -> bytes:
    """SVG con un atributo de script: el vector de XSS que la lista blanca excluye."""
    return (
        b'<?xml version="1.0" encoding="UTF-8"?>\n'
        b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" onload="alert(1)"/>\n'
    )


def _zip_sin_parte_de_libro() -> bytes:
    """`[Content_Types].xml` con hojas y estilos, pero sin la parte de libro de `.xlsx`."""
    return _zip(
        {
            "[Content_Types].xml": _content_types(
                ("/xl/worksheets/sheet1.xml", PARTE_HOJA),
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


def _xlsm() -> bytes:
    """Libro con macros: su parte principal es la de `.xlsm`, no la de `.xlsx`."""
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


def _xml_con_entidades() -> bytes:
    """«Mil millones de risas»: diez niveles de diez referencias, sin expandir."""
    definiciones = ['<!ENTITY lol "lol">']
    for nivel in range(1, 10):
        definiciones.append(f'<!ENTITY lol{nivel} "' + f"&lol{nivel - 1};" * 10 + '">')
    cuerpo = "\n".join(definiciones)
    texto = '<?xml version="1.0"?>\n<!DOCTYPE lolz [\n' + cuerpo + "\n]>\n<lolz>&lol9;</lolz>\n"
    return texto.encode("utf-8")


# --------------------------------------------------------------------------- la escena


@dataclass(frozen=True)
class Fotografia:
    """Todo lo que un rechazo no debe cambiar, tal como lo ve una conexión nueva."""

    fila: dict[str, Any]
    asientos_del_archivo: list[dict[str, Any]]
    bitacora_sin_denegar: int
    denegaciones: list[dict[str, Any]]
    tipo_del_objeto: str | None


@dataclass
class Escena:
    """La aplicación real con `archivos` montado, un cliente HTTPS abierto y un Director con sesión."""

    cliente: TestClient
    aplicacion: FastAPI
    motor: Engine
    reloj: RelojDePrueba
    contador: AlmacenContador
    registro: io.StringIO
    s3: S3Client
    bucket: str
    sembrar_usuario: SembrarUsuario
    director_id: uuid.UUID
    sesion_id: uuid.UUID

    def alta(
        self,
        contenido: bytes,
        *,
        nombre_original: str = NOMBRE_DEL_LIBRO,
        tipo_declarado: str = TIPO_XLSX,
    ) -> ArchivoSubido:
        """Alta por la interfaz publicada, a nombre del Director: declara el tamaño y la suma de `contenido`."""
        return dar_de_alta(
            self.aplicacion,
            self.motor,
            usuario_id=self.director_id,
            contenido=contenido,
            nombre_original=nombre_original,
            tipo_declarado=tipo_declarado,
        )

    def subir(self, archivo: ArchivoSubido) -> None:
        subir_objeto(archivo)

    def sembrar_objeto(self, archivo: ArchivoSubido, contenido: bytes, *, con_suma: bool) -> None:
        """Escribe `contenido` bajo la clave del archivo, saltándose la URL prefirmada y su firma."""
        if con_suma:
            suma = base64.b64encode(hashlib.sha256(contenido).digest()).decode("ascii")
            self.s3.put_object(
                Bucket=self.bucket, Key=archivo.clave, Body=contenido, ChecksumSHA256=suma
            )
        else:
            self.s3.put_object(Bucket=self.bucket, Key=archivo.clave, Body=contenido)

    def suma_guardada_del_objeto(self, archivo: ArchivoSubido) -> str | None:
        cabeza = self.s3.head_object(Bucket=self.bucket, Key=archivo.clave, ChecksumMode="ENABLED")
        return cabeza.get("ChecksumSHA256")

    def confirmar(self, archivo_id: uuid.UUID, *, sesion_id: uuid.UUID | None = None) -> Respuesta:
        return confirmar_por_http(
            self.cliente, self.sesion_id if sesion_id is None else sesion_id, archivo_id
        )

    def usuario_con_roles(self, correo: str, roles: tuple[str, ...]) -> tuple[uuid.UUID, uuid.UUID]:
        """Un usuario real con esos roles y su sesión abierta por HTTP: `(usuario_id, sesion_id)`."""
        usuario_id = self.sembrar_usuario(
            correo, CONTRASENA_DE_PRUEBA, roles=roles, nombre=NOMBRE_DEL_DIRECTOR
        )
        return usuario_id, iniciar_sesion(self.cliente, correo, CONTRASENA_DE_PRUEBA)

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

    def fijar_creado_en(self, archivo: ArchivoSubido, creado_en: datetime) -> None:
        with self.motor.begin() as conexion:
            conexion.execute(
                text("UPDATE archivo SET creado_en = :creado_en WHERE id = :id"),
                {"creado_en": creado_en, "id": archivo.archivo_id},
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
        try:
            tipo = self.s3.head_object(Bucket=self.bucket, Key=archivo.clave)["ContentType"]
        except ClientError:
            tipo = None
        return Fotografia(
            fila=dict(fila),
            asientos_del_archivo=asientos_del_archivo(self.motor, archivo.archivo_id),
            bitacora_sin_denegar=sin_denegar,
            denegaciones=denegaciones,
            tipo_del_objeto=tipo,
        )

    def total_de_la_bitacora(self) -> int:
        with self.motor.connect() as conexion:
            return conexion.execute(text("SELECT count(*) FROM bitacora")).scalar_one()


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
    contador = AlmacenContador(almacen)
    aplicacion = crear_aplicacion_de_archivos(
        almacen=contador.como_almacen(),
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
            contador=contador,
            registro=registro_tecnico,
            s3=cliente_s3,
            bucket=bucket_de_pruebas,
            sembrar_usuario=sembrar_usuario,
            director_id=director_id,
            sesion_id=abrir_sesion_del_director(cliente),
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


def _exigir_permiso(
    respuesta: Respuesta, *, motivo: str, mensaje: str, roles_requeridos: list[str]
) -> None:
    """El contrato de un `403 PERMISO`: cuerpo exacto, sin `detalle` y sin datos del recurso."""
    _exigir_error(
        respuesta,
        estado=403,
        esperado={
            "tipo": "PERMISO",
            "motivo": motivo,
            "mensaje": mensaje,
            "roles_requeridos": roles_requeridos,
        },
        esquema="ErrorPermiso",
    )


def _sin_datos_del_archivo(respuesta: Respuesta, archivo: ArchivoSubido) -> None:
    for dato in (
        str(archivo.archivo_id),
        str(archivo.obra_id),
        archivo.nombre_original,
        archivo.hash_sha256,
        archivo.clave,
        "detalle",
    ):
        assert dato not in respuesta.text, f"El 403 no puede revelar {dato!r}"


def _denegacion(
    escena: Escena,
    *,
    usuario_id: uuid.UUID,
    motivo: str,
    archivo_id: uuid.UUID,
    roles_requeridos: list[str],
) -> dict[str, Any]:
    """El asiento `DENEGAR` que debe quedar, a nombre de quien llamó (modelo de datos §10, C-1 enmendado)."""
    return {
        "usuario_id": usuario_id,
        "ocurrido_en": escena.reloj.ahora,
        "motivo": motivo,
        "regla_negocio": None,
        "entidad_tipo": "usuario",
        "entidad_id": usuario_id,
        "obra_id": None,
        "datos_antes_es_nulo": True,
        "datos_despues": {
            "metodo": "POST",
            "ruta": ruta_de_confirmacion(archivo_id),
            "roles_requeridos": roles_requeridos,
        },
    }


def _exigir_denegacion_nueva(
    antes: Fotografia, despues: Fotografia, esperada: dict[str, Any]
) -> None:
    """Un solo `DENEGAR` nuevo y nada más: la fila, los asientos del archivo y el almacén no cambiaron."""
    assert despues.denegaciones == [*antes.denegaciones, esperada]
    assert replace(despues, denegaciones=antes.denegaciones) == antes


def _contenido_de_documento(tamano: int, byte: bytes) -> bytes:
    return byte * tamano


# --------------------------------------------------------------------------- TC-19


def test_hdu001_esc25_tamano_distinto(escena: Escena) -> None:
    """HDU-001 esc. 25 · TC-19 · CA-5 esc. 1 · RNF-19 — el objeto almacenado pesa menos que lo declarado: `409` `ARCHIVO_TAMANO_DISTINTO`.

    Se declaran 8 388 608 bytes y se siembra, por un cliente directo, un objeto de 8 126 464. El `409` lleva
    los dos tamaños como enteros y ninguna acción; la fila sigue `PENDIENTE`, el objeto conserva su tipo, no
    se leyó ningún rango (el tipo no se mira si el tamaño no coincide) y la bitácora no recibe nada. El
    tamaño se compara antes que la suma: el objeto sembrado no lleva suma, y de compararse ella primero la
    respuesta sería `ARCHIVO_HASH_DISTINTO`.
    """
    declarado = _contenido_de_documento(8_388_608, b"a")
    almacenado = _contenido_de_documento(8_126_464, b"b")
    archivo = escena.alta(declarado)
    escena.sembrar_objeto(archivo, almacenado, con_suma=False)
    antes = escena.fotografiar(archivo)

    respuesta = escena.confirmar(archivo.archivo_id)

    _exigir_conflicto(
        respuesta,
        codigo="ARCHIVO_TAMANO_DISTINTO",
        mensaje=MENSAJE_TAMANO,
        detalle={"tamano_declarado": 8_388_608, "tamano_almacenado": 8_126_464},
    )
    assert antes.fila["estado"] == "PENDIENTE"
    assert escena.fotografiar(archivo) == antes
    assert escena.contador.llamadas_metadatos == [archivo.clave]
    assert escena.contador.rangos_leidos == []
    assert escena.contador.reescrituras == []


# --------------------------------------------------------------------------- TC-20


@pytest.mark.parametrize(
    "con_suma", [True, False], ids=["con_suma_almacenada", "sin_suma_almacenada"]
)
def test_hdu001_esc25_hash_distinto(escena: Escena, con_suma: bool) -> None:
    """HDU-001 esc. 25 · TC-20 · CA-5 esc. 2 · RNF-19 · P-11 — mismo tamaño y otro contenido: `409` `ARCHIVO_HASH_DISTINTO`.

    Con suma almacenada, el `detalle` trae los dos SHA-256 en hexadecimal y los dos tamaños, que coinciden.
    Sin suma almacenada (el objeto se sembró sin `ChecksumSHA256`), el código es el mismo y el `detalle`
    **omite** `hash_almacenado`: una suma ausente cuenta como distinta, nunca como igual. El mensaje invita
    a volver a cargar el archivo. La fila sigue `PENDIENTE` y no se asienta nada.
    """
    declarado = b"A" * 4096
    almacenado = b"B" * 4096
    archivo = escena.alta(declarado)
    escena.sembrar_objeto(archivo, almacenado, con_suma=con_suma)
    suma_guardada = escena.suma_guardada_del_objeto(archivo)
    if con_suma:
        assert suma_guardada == base64.b64encode(hashlib.sha256(almacenado).digest()).decode(
            "ascii"
        )
    else:
        assert suma_guardada is None, (
            "La siembra sin suma no debe dejar ninguna suma SHA-256 en el objeto"
        )
    antes = escena.fotografiar(archivo)

    respuesta = escena.confirmar(archivo.archivo_id)

    detalle: dict[str, Any] = {
        "hash_declarado": hashlib.sha256(declarado).hexdigest(),
        "tamano_declarado": 4096,
        "tamano_almacenado": 4096,
    }
    if con_suma:
        detalle["hash_almacenado"] = hashlib.sha256(almacenado).hexdigest()
    _exigir_conflicto(
        respuesta, codigo="ARCHIVO_HASH_DISTINTO", mensaje=MENSAJE_HASH, detalle=detalle
    )
    assert "Vuelve a cargar el archivo" in respuesta.json()["mensaje"]
    assert ("hash_almacenado" in respuesta.json()["detalle"]) is con_suma
    assert escena.fotografiar(archivo) == antes
    assert antes.fila["estado"] == "PENDIENTE"
    assert escena.contador.rangos_leidos == []
    assert escena.contador.reescrituras == []


# --------------------------------------------------------------------------- TC-22


CASOS_DE_TIPO_NO_PERMITIDO = [
    pytest.param(
        _ejecutable_mz(), "application/vnd.microsoft.portable-executable", id="ejecutable_mz"
    ),
    pytest.param(_svg(), "image/svg+xml", id="svg"),
    pytest.param(_zip_sin_parte_de_libro(), "application/zip", id="zip_sin_parte_de_libro"),
    pytest.param(_zip_sin_content_types(), "application/zip", id="zip_sin_content_types"),
    pytest.param(_xlsm(), "application/zip", id="xlsm"),
]


@pytest.mark.parametrize(("contenido", "tipo_detectado"), CASOS_DE_TIPO_NO_PERMITIDO)
def test_hdu001_esc26_tipo_no_permitido(
    escena: Escena, contenido: bytes, tipo_detectado: str
) -> None:
    """HDU-001 esc. 26 · TC-22 · CA-6 esc. 1 · RNF-06 — declarado `.xlsx`, el contenido no lo es: `409` `ARCHIVO_TIPO_NO_PERMITIDO`.

    El tamaño y la suma coinciden (el objeto se subió por la URL prefirmada), así que el rechazo sale de
    leer el tipo de los **bytes**: un ejecutable, un SVG, un ZIP con `[Content_Types].xml` sin parte de
    libro, un ZIP sin `[Content_Types].xml` y un `.xlsm`. El `detalle` trae el tipo detectado y la lista de
    los ocho tipos admitidos en su orden. La fila sigue `PENDIENTE` y el objeto conserva su
    `application/octet-stream`: no se reescribió ni se asentó nada.
    """
    archivo = escena.alta(contenido, tipo_declarado=TIPO_XLSX)
    escena.subir(archivo)
    antes = escena.fotografiar(archivo)

    respuesta = escena.confirmar(archivo.archivo_id)

    _exigir_conflicto(
        respuesta,
        codigo="ARCHIVO_TIPO_NO_PERMITIDO",
        mensaje=MENSAJE_TIPO,
        detalle={"tipo_detectado": tipo_detectado, "tipos_admitidos": TIPOS_ADMITIDOS},
    )
    assert antes.fila["estado"] == "PENDIENTE"
    assert escena.fotografiar(archivo) == antes
    assert escena.contador.rangos_leidos, "El tipo se decide leyendo los bytes del objeto"
    assert escena.contador.reescrituras == []
    assert escena.contador.llamadas_leer_todo == []


# --------------------------------------------------------------------------- TC-23


def test_tkt059_ca06_svg_renombrado_a_jpg(escena: Escena) -> None:
    """TC-23 · CA-6 esc. 2 · RNF-06 — un SVG declarado `image/jpeg` y llamado `foto.jpg` se detecta como SVG.

    El tipo sale de los bytes, nunca de la extensión ni de lo que declare el cliente: `tipo_detectado` es
    `image/svg+xml` y el archivo no se confirma.
    """
    archivo = escena.alta(_svg(), nombre_original="foto.jpg", tipo_declarado="image/jpeg")
    escena.subir(archivo)
    antes = escena.fotografiar(archivo)

    respuesta = escena.confirmar(archivo.archivo_id)

    _exigir_conflicto(
        respuesta,
        codigo="ARCHIVO_TIPO_NO_PERMITIDO",
        mensaje=MENSAJE_TIPO,
        detalle={"tipo_detectado": "image/svg+xml", "tipos_admitidos": TIPOS_ADMITIDOS},
    )
    assert respuesta.json()["detalle"]["tipo_detectado"] == "image/svg+xml"
    assert escena.fotografiar(archivo) == antes
    assert antes.fila["estado"] == "PENDIENTE"
    assert antes.fila["nombre_original"] == "foto.jpg"
    assert escena.contador.reescrituras == []


# --------------------------------------------------------------------------- TC-24


def test_tkt059_ca06_xml_con_entidades(escena: Escena) -> None:
    """TC-24 · CA-6 esc. 3 · RNF-06 — un XML de «mil millones de risas» se rechaza sin expandirse y en menos de 5 s.

    Declarado `application/xml`, su DTD define entidades anidadas; el analizador con `forbid_dtd`,
    `forbid_entities` y `forbid_external` no las expande y el detector responde `application/xml-dtd`, que
    no está en la lista blanca. La confirmación completa tarda menos de cinco segundos.
    """
    archivo = escena.alta(
        _xml_con_entidades(), nombre_original="comprobante.xml", tipo_declarado="application/xml"
    )
    escena.subir(archivo)
    antes = escena.fotografiar(archivo)

    inicio = time.perf_counter()
    respuesta = escena.confirmar(archivo.archivo_id)
    duracion = time.perf_counter() - inicio

    _exigir_conflicto(
        respuesta,
        codigo="ARCHIVO_TIPO_NO_PERMITIDO",
        mensaje=MENSAJE_TIPO,
        detalle={"tipo_detectado": "application/xml-dtd", "tipos_admitidos": TIPOS_ADMITIDOS},
    )
    assert duracion < LIMITE_DE_LA_EXPANSION_SEGUNDOS, f"La confirmación tardó {duracion:.2f} s"
    assert escena.fotografiar(archivo) == antes
    assert escena.contador.reescrituras == []


# --------------------------------------------------------------------------- TC-26


def test_tkt059_ca07_objeto_nunca_subido(escena: Escena) -> None:
    """TC-26 · CA-7 esc. 1 · RNF-19 — el alta existe pero nadie subió el objeto: `409` `ARCHIVO_NO_SUBIDO` con el `archivo_id`.

    El `PUT` nunca ocurrió, así que `metadatos` devuelve `None`. El `detalle` es solo `{"archivo_id"}`; la
    fila sigue `PENDIENTE`, no se leyó ningún rango y no se asentó nada.
    """
    archivo = escena.alta(b"contenido que nadie subio" * 100)
    antes = escena.fotografiar(archivo)
    assert antes.tipo_del_objeto is None, "El objeto no debe existir en el almacén"

    respuesta = escena.confirmar(archivo.archivo_id)

    _exigir_conflicto(
        respuesta,
        codigo="ARCHIVO_NO_SUBIDO",
        mensaje=MENSAJE_NO_SUBIDO,
        detalle={"archivo_id": str(archivo.archivo_id)},
    )
    assert antes.fila["estado"] == "PENDIENTE"
    assert escena.fotografiar(archivo) == antes
    assert escena.contador.llamadas_metadatos == [archivo.clave]
    assert escena.contador.rangos_leidos == []
    assert escena.contador.reescrituras == []


# --------------------------------------------------------------------------- TC-27


def test_tkt059_ca07_confirmar_un_caducado(escena: Escena) -> None:
    """TC-27 · CA-7 esc. 2 · PA-T59.13 — una fila `CADUCADO` no se confirma aunque su objeto sí llegó: `409` `ARCHIVO_CADUCADO`.

    El objeto está completo y es un `.xlsx` válido, de modo que sin el paso 4 la confirmación terminaría en
    `200`. El `detalle` lleva el `archivo_id` y `estado_archivo` `CADUCADO`. La fila queda igual, la
    bitácora no recibe ningún asiento y el almacén ni se consulta.
    """
    archivo = escena.alta(_zip_xlsx_valido())
    escena.subir(archivo)
    escena.poner_estado(archivo, "CADUCADO")
    antes = escena.fotografiar(archivo)

    respuesta = escena.confirmar(archivo.archivo_id)

    _exigir_conflicto(
        respuesta,
        codigo="ARCHIVO_CADUCADO",
        mensaje=MENSAJE_CADUCADO,
        detalle={"archivo_id": str(archivo.archivo_id), "estado_archivo": "CADUCADO"},
    )
    assert antes.fila["estado"] == "CADUCADO"
    assert escena.fotografiar(archivo) == antes
    assert asientos_del_archivo(escena.motor, archivo.archivo_id) == []
    assert escena.contador.llamadas_metadatos == []
    assert escena.contador.reescrituras == []


def _zip_xlsx_valido() -> bytes:
    """Un libro mínimo que el detector reconoce como `.xlsx`: confirmable si nada lo impide."""
    return _zip(
        {
            "[Content_Types].xml": _content_types(("/xl/workbook.xml", PARTE_XLSX)),
            "xl/workbook.xml": b"<workbook/>",
        }
    )


# --------------------------------------------------------------------------- TC-28


def test_tkt059_ca07_pendiente_vencido_sin_barrer(escena: Escena) -> None:
    """TC-28 · CA-7 esc. 3 · PA-T59.13 — un `PENDIENTE` de hace 24 h y 1 s se confirma como vencido: `409` `ARCHIVO_CADUCADO` y la fila pasa a `CADUCADO`.

    `creado_en = reloj − 24 h − 1 s` y el objeto coincide con lo declarado. El `409` se lanza **después** de
    confirmar la transacción: leída desde otra conexión, la fila ya está `CADUCADO`, y es lo único que
    cambió. No hay `CONFIRMAR` ni ninguna otra escritura en la bitácora, `metadatos` no se llamó y el
    objeto no se reescribió. Mutante `M-10`: lanzar dentro del bloque deshace el `UPDATE`.
    """
    archivo = escena.alta(_zip_xlsx_valido())
    escena.subir(archivo)
    assert escena.aplicacion.state.archivos.configuracion.umbral_pendiente == UMBRAL_DE_PENDIENTE
    escena.fijar_creado_en(archivo, escena.reloj.ahora - UMBRAL_DE_PENDIENTE - timedelta(seconds=1))
    antes = escena.fotografiar(archivo)
    assert antes.fila["estado"] == "PENDIENTE"

    respuesta = escena.confirmar(archivo.archivo_id)

    _exigir_conflicto(
        respuesta,
        codigo="ARCHIVO_CADUCADO",
        mensaje=MENSAJE_CADUCADO,
        detalle={"archivo_id": str(archivo.archivo_id), "estado_archivo": "CADUCADO"},
    )
    despues = escena.fotografiar(archivo)
    assert despues.fila["estado"] == "CADUCADO", "El UPDATE a CADUCADO debe haberse confirmado"
    assert despues.fila == {**antes.fila, "estado": "CADUCADO"}
    assert despues.asientos_del_archivo == []
    assert asientos_del_archivo(escena.motor, archivo.archivo_id, "CONFIRMAR") == []
    assert replace(despues, fila=antes.fila) == antes
    assert escena.contador.llamadas_metadatos == []
    assert escena.contador.reescrituras == []


def test_tkt059_ca07_pendiente_en_el_borde_exacto_se_confirma(escena: Escena) -> None:
    """TC-28 (borde) · CA-7 esc. 3 · PA-T59.13 — con `creado_en = reloj − 24 h` exactos el archivo todavía se confirma: `200`.

    El vencimiento es `vence_en < ahora`: en el instante exacto no vence. Mutante `M-01`: `not ahora <
    vence_en` lo daría por vencido.
    """
    archivo = escena.alta(_zip_xlsx_valido())
    escena.subir(archivo)
    escena.fijar_creado_en(archivo, escena.reloj.ahora - UMBRAL_DE_PENDIENTE)

    respuesta = escena.confirmar(archivo.archivo_id)

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["estado"] == "DISPONIBLE"
    assert respuesta.json()["tipo_mime"] == TIPO_XLSX
    despues = escena.fotografiar(archivo)
    assert despues.fila["estado"] == "DISPONIBLE"
    assert despues.fila["confirmado_en"] == escena.reloj.ahora
    assert len(asientos_del_archivo(escena.motor, archivo.archivo_id, "CONFIRMAR")) == 1


# --------------------------------------------------------------------------- TC-29


@pytest.mark.parametrize("estado", ["PENDIENTE", "CADUCADO", "ANULADO", "DISPONIBLE"])
def test_tkt059_ca07_otro_director_no_confirma(escena: Escena, estado: str) -> None:
    """TC-29 · CA-7 esc. 4 · PA-T59.8 — otro Director no confirma lo que subió alguien más: `403` `PERMISO` `NO_ES_SOLICITANTE`.

    Cuerpo exacto: `roles_requeridos` vacío, sin `detalle` y sin dato alguno del archivo. Se asienta un
    único `DENEGAR` a nombre de quien intentó, con el motivo, el método, la ruta y el rol exigido. El
    solicitante se evalúa **antes** que el estado, así que la respuesta es la misma con la fila
    `PENDIENTE`, `CADUCADO` (`M-02b`), `ANULADO` o `DISPONIBLE`: un `403` nunca revela el estado. La fila,
    los asientos del archivo y el objeto no cambian, y el almacén ni se consulta.
    """
    archivo = escena.alta(_zip_xlsx_valido())
    escena.subir(archivo)
    if estado == "DISPONIBLE":
        propia = escena.confirmar(archivo.archivo_id)
        assert propia.status_code == 200, propia.text
        escena.contador.llamadas_metadatos.clear()
        escena.contador.reescrituras.clear()
    elif estado != "PENDIENTE":
        escena.poner_estado(archivo, estado)
    otro_id, sesion_del_otro = escena.usuario_con_roles(
        CORREO_OTRO_DIRECTOR, (ROL_DE_CONFIRMACION,)
    )
    antes = escena.fotografiar(archivo)
    assert antes.fila["estado"] == estado

    respuesta = escena.confirmar(archivo.archivo_id, sesion_id=sesion_del_otro)

    _exigir_permiso(
        respuesta, motivo="NO_ES_SOLICITANTE", mensaje=MENSAJE_NO_SOLICITANTE, roles_requeridos=[]
    )
    _sin_datos_del_archivo(respuesta, archivo)
    despues = escena.fotografiar(archivo)
    _exigir_denegacion_nueva(
        antes,
        despues,
        _denegacion(
            escena,
            usuario_id=otro_id,
            motivo="NO_ES_SOLICITANTE",
            archivo_id=archivo.archivo_id,
            roles_requeridos=[ROL_DE_CONFIRMACION],
        ),
    )
    assert despues.fila["estado"] == estado
    assert escena.contador.llamadas_metadatos == []
    assert escena.contador.reescrituras == []


def test_tkt059_ca07_si_la_bitacora_falla_el_403_sigue(
    escena: Escena, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TC-29b · CA-7 esc. 4 · PA-T59.8 · RNF-13 — si la bitácora no asienta la denegación, el `403` `NO_ES_SOLICITANTE` sigue igual.

    `auditoria.asentar_denegacion` se sustituye por una función que lanza `RuntimeError`. La respuesta es
    el mismo `403` exacto de TC-29, sin dato alguno del archivo; no es un `500`. El fallo queda en el
    registro técnico como un único evento `denegacion_no_asentada`, nivel `error`, con la correlación de
    la respuesta, el usuario que intentó y el **tipo** de la excepción (`tipo_error`), nunca su texto. La
    fila, los asientos del archivo, las denegaciones y el objeto no cambian. Mutante: quitar el
    `try/except` de `_asentar_denegacion` convierte el `403` en un `500`.
    """
    from cimenta.archivos.aplicacion import confirmacion

    archivo = escena.alta(_zip_xlsx_valido())
    escena.subir(archivo)
    otro_id, sesion_del_otro = escena.usuario_con_roles(
        CORREO_OTRO_DIRECTOR, (ROL_DE_CONFIRMACION,)
    )
    antes = escena.fotografiar(archivo)

    def asentar_que_falla(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("bitácora caída")

    monkeypatch.setattr(confirmacion.auditoria, "asentar_denegacion", asentar_que_falla)

    respuesta = escena.confirmar(archivo.archivo_id, sesion_id=sesion_del_otro)

    _exigir_permiso(
        respuesta, motivo="NO_ES_SOLICITANTE", mensaje=MENSAJE_NO_SOLICITANTE, roles_requeridos=[]
    )
    _sin_datos_del_archivo(respuesta, archivo)
    assert escena.fotografiar(archivo) == antes, "Sin asiento DENEGAR y sin ningún otro cambio"
    lineas = [
        json.loads(linea) for linea in escena.registro.getvalue().splitlines() if linea.strip()
    ]
    (evento,) = [linea for linea in lineas if linea["event"] == "denegacion_no_asentada"]
    assert evento["level"] == "error"
    assert evento["usuario_id"] == str(otro_id)
    assert evento["tipo_error"] == "RuntimeError"
    assert evento["correlacion_id"] == respuesta.headers[CABECERA_CORRELACION]
    texto_del_registro = json.dumps(lineas, ensure_ascii=False)
    assert "bitácora caída" not in texto_del_registro
    assert "caída" not in escena.registro.getvalue()
    assert "ca\\u00edda" not in escena.registro.getvalue()
    assert escena.contador.llamadas_metadatos == []


# --------------------------------------------------------------------------- TC-30


@pytest.mark.parametrize("rol", ROLES_SIN_PERMISO)
def test_tkt059_ca07_sin_rol(escena: Escena, rol: str) -> None:
    """TC-30 · CA-7 esc. 5 · RN-04 — sin `DIRECTOR_PROYECTOS`: `403` `PERMISO` `ROL_INSUFICIENTE`, sin datos del archivo y con un `DENEGAR`.

    Los cinco roles restantes, con sesión y token CSRF válidos. Cuerpo exacto con `roles_requeridos`
    `["DIRECTOR_PROYECTOS"]` (el `x-roles` del borrador), sin `detalle` ni identificadores. El asiento
    `DENEGAR` es de quien llamó, con `ROL_INSUFICIENTE`, `POST` y la ruta. El archivo ni se mira: la fila,
    sus asientos y el almacén quedan como estaban.
    """
    archivo = escena.alta(_zip_xlsx_valido())
    escena.subir(archivo)
    usuario_id, sesion = escena.usuario_con_roles(f"{rol.lower()}.archivos@cimenta.test", (rol,))
    antes = escena.fotografiar(archivo)

    respuesta = escena.confirmar(archivo.archivo_id, sesion_id=sesion)

    _exigir_permiso(
        respuesta,
        motivo="ROL_INSUFICIENTE",
        mensaje=MENSAJE_ROL_INSUFICIENTE,
        roles_requeridos=[ROL_DE_CONFIRMACION],
    )
    _sin_datos_del_archivo(respuesta, archivo)
    _exigir_denegacion_nueva(
        antes,
        escena.fotografiar(archivo),
        _denegacion(
            escena,
            usuario_id=usuario_id,
            motivo="ROL_INSUFICIENTE",
            archivo_id=archivo.archivo_id,
            roles_requeridos=[ROL_DE_CONFIRMACION],
        ),
    )
    assert escena.contador.llamadas_metadatos == []


def test_tkt059_ca07_el_rol_se_comprueba_antes_que_la_existencia(escena: Escena) -> None:
    """TC-30 · CA-7 esc. 5 · conv-seguridad — quien no tiene rol recibe `403` aunque el archivo no exista: no se averigua qué existe."""
    usuario_id, sesion = escena.usuario_con_roles("residente.archivos@cimenta.test", ("RESIDENTE",))
    inexistente = uuid.uuid4()
    with escena.motor.connect() as conexion:
        denegaciones_antes = [
            dict(fila) for fila in conexion.execute(text(SQL_DENEGACIONES)).mappings().all()
        ]

    respuesta = escena.confirmar(inexistente, sesion_id=sesion)

    _exigir_permiso(
        respuesta,
        motivo="ROL_INSUFICIENTE",
        mensaje=MENSAJE_ROL_INSUFICIENTE,
        roles_requeridos=[ROL_DE_CONFIRMACION],
    )
    with escena.motor.connect() as conexion:
        denegaciones = [dict(f) for f in conexion.execute(text(SQL_DENEGACIONES)).mappings().all()]
    assert denegaciones == [
        *denegaciones_antes,
        _denegacion(
            escena,
            usuario_id=usuario_id,
            motivo="ROL_INSUFICIENTE",
            archivo_id=inexistente,
            roles_requeridos=[ROL_DE_CONFIRMACION],
        ),
    ]


@pytest.mark.parametrize(("cookie", "cabecera"), SIN_PAR_VALIDO)
def test_tkt059_ca07_sin_origen(escena: Escena, cookie: str | None, cabecera: str | None) -> None:
    """TC-30 · CA-7 esc. 5 · RNF-05 — con sesión y sin par CSRF válido: `403` `PERMISO` `ORIGEN_NO_VERIFICADO` y un `DENEGAR`.

    Las cuatro combinaciones del doble envío: ambos ausentes, solo la cookie, solo la cabecera y valores
    distintos. La operación no se ejecuta: la fila, los asientos del archivo y el almacén no cambian. El
    `DENEGAR` es de quien tiene la sesión, con `roles_requeridos` vacío (el origen no es cuestión de rol).
    """
    archivo = escena.alta(_zip_xlsx_valido())
    escena.subir(archivo)
    antes = escena.fotografiar(archivo)

    respuesta = escena.cliente.post(
        ruta_de_confirmacion(archivo.archivo_id),
        headers=cabeceras_de(escena.sesion_id, cookie, cabecera),
    )

    _exigir_permiso(
        respuesta,
        motivo="ORIGEN_NO_VERIFICADO",
        mensaje=MENSAJE_ORIGEN_NO_VERIFICADO,
        roles_requeridos=[],
    )
    _sin_datos_del_archivo(respuesta, archivo)
    _exigir_denegacion_nueva(
        antes,
        escena.fotografiar(archivo),
        _denegacion(
            escena,
            usuario_id=escena.director_id,
            motivo="ORIGEN_NO_VERIFICADO",
            archivo_id=archivo.archivo_id,
            roles_requeridos=[],
        ),
    )
    assert escena.contador.llamadas_metadatos == []


def test_tkt059_ca07_el_origen_se_comprueba_antes_que_el_rol(escena: Escena) -> None:
    """TC-30 · CA-7 esc. 5 · RNF-05 — sin par CSRF y sin rol: gana `ORIGEN_NO_VERIFICADO`, porque `verificar_origen` va antes que `exigir_rol`.

    Mutante «invertir el orden de las dependencias»: respondería `ROL_INSUFICIENTE`.
    """
    archivo = escena.alta(_zip_xlsx_valido())
    escena.subir(archivo)
    usuario_id, sesion = escena.usuario_con_roles("almacen.archivos@cimenta.test", ("ALMACEN",))
    antes = escena.fotografiar(archivo)

    respuesta = escena.cliente.post(
        ruta_de_confirmacion(archivo.archivo_id), headers=cabeceras_de(sesion, None, None)
    )

    _exigir_permiso(
        respuesta,
        motivo="ORIGEN_NO_VERIFICADO",
        mensaje=MENSAJE_ORIGEN_NO_VERIFICADO,
        roles_requeridos=[],
    )
    _exigir_denegacion_nueva(
        antes,
        escena.fotografiar(archivo),
        _denegacion(
            escena,
            usuario_id=usuario_id,
            motivo="ORIGEN_NO_VERIFICADO",
            archivo_id=archivo.archivo_id,
            roles_requeridos=[],
        ),
    )


def test_tkt059_ca07_archivo_inexistente(escena: Escena) -> None:
    """TC-30 · CA-7 esc. 5 — un identificador que no existe: `404` `NO_ENCONTRADO` con `recurso` `archivo`.

    Cuerpo exacto con el mensaje del diseño. No se asienta nada y el almacén no se consulta.
    """
    antes = escena.total_de_la_bitacora()
    inexistente = uuid.uuid4()

    respuesta = escena.confirmar(inexistente)

    _exigir_error(
        respuesta,
        estado=404,
        esperado={"tipo": "NO_ENCONTRADO", "mensaje": MENSAJE_NO_EXISTE, "recurso": "archivo"},
        esquema="ErrorNoEncontrado",
    )
    assert escena.total_de_la_bitacora() == antes
    assert escena.contador.llamadas_metadatos == []


@pytest.mark.parametrize("sesion", ["sin_cookie", "sesion_inexistente"])
def test_tkt059_ca07_sin_sesion(escena: Escena, sesion: str) -> None:
    """TC-30 · CA-7 esc. 5 · RNF-13 — sin sesión (o con una que no existe): `401` `SESION` `SIN_SESION`, aun con par CSRF válido.

    La sesión se evalúa antes que el token y que el rol. El cuerpo no revela nada del archivo, que existe;
    la fila y la bitácora quedan como estaban (un rechazo anónimo no se asienta).
    """
    archivo = escena.alta(_zip_xlsx_valido())
    escena.subir(archivo)
    antes = escena.fotografiar(archivo)

    respuesta = escena.cliente.post(
        ruta_de_confirmacion(archivo.archivo_id),
        headers=cabeceras_de(
            uuid.uuid4() if sesion == "sesion_inexistente" else None, TOKEN_CSRF, TOKEN_CSRF
        ),
    )

    _exigir_error(
        respuesta,
        estado=401,
        esperado={"tipo": "SESION", "motivo": "SIN_SESION", "mensaje": MENSAJE_SIN_SESION},
        esquema="ErrorSesion",
    )
    _sin_datos_del_archivo(respuesta, archivo)
    assert escena.fotografiar(archivo) == antes
    assert escena.contador.llamadas_metadatos == []


# --------------------------------------------------------------------------- caso extra (P-10)


def test_tkt059_ca07_confirmar_un_anulado(escena: Escena) -> None:
    """Extra · P-10 — una fila `ANULADO` no se confirma: `409` `CONFLICTO` `ESTADO_NO_PERMITE_OPERACION`.

    `ANULADO` es inalcanzable por la API en este ticket (la anulación llega después), así que la fila se
    siembra por SQL, con autor y motivo. El `detalle` lleva el `archivo_id` y `estado_archivo` `ANULADO`,
    la fila queda igual, no se asienta nada y el almacén ni se consulta. El objeto está completo y es un
    `.xlsx` válido: sin el paso 5, la confirmación terminaría en `200`.
    """
    archivo = escena.alta(_zip_xlsx_valido())
    escena.subir(archivo)
    escena.poner_estado(archivo, "ANULADO")
    antes = escena.fotografiar(archivo)

    respuesta = escena.confirmar(archivo.archivo_id)

    _exigir_conflicto(
        respuesta,
        codigo="ESTADO_NO_PERMITE_OPERACION",
        mensaje=MENSAJE_ANULADO,
        detalle={"archivo_id": str(archivo.archivo_id), "estado_archivo": "ANULADO"},
    )
    assert antes.fila["estado"] == "ANULADO"
    assert escena.fotografiar(archivo) == antes
    assert escena.contador.llamadas_metadatos == []
    assert escena.contador.reescrituras == []
