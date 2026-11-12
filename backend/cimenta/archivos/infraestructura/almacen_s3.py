"""Adaptador del almacén de objetos sobre la API S3 (TKT-059, RNF-06, RNF-19 y ADR-016).

El almacén es cualquier servicio compatible con la API S3: el adaptador no nombra ningún proveedor.
Lo que cambia entre entornos son solo las direcciones que llegan por configuración. Dos clientes
con estas responsabilidades:

- `firmante` solo firma URL prefirmadas (subida y lectura). Apunta al origen público, porque la
  firma incluye el host y el navegador lo tiene que reproducir.
- `cliente` hace las operaciones del servidor (metadatos, lectura, copia). Apunta al endpoint
  interno si existe, y si no, al origen.

Las rutas de la API nunca leen ni escriben el contenido (ADR-016): el adaptador lo sirve el
lector del ejecutor y el navegador por URL prefirmada. La suma SHA-256 viaja firmada en la subida
(E-1): si el cuerpo no coincide, el almacén rechaza el PUT. Sin reloj: los plazos llegan como
`timedelta`.
"""

from __future__ import annotations

import base64
from datetime import timedelta
from typing import TYPE_CHECKING
from urllib.parse import quote

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from cimenta.archivos.dominio.confirmacion import ObjetoAlmacenado
from cimenta.archivos.dominio.url_firmada import UrlFirmada

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

REGION = "us-east-1"
CABECERA_SUMA = "x-amz-checksum-sha256"
AUSENCIAS = frozenset({"404", "NoSuchKey", "NotFound"})


def _suma_base64(sha256_hex: str) -> str:
    """El SHA-256 en binario, en base64: la forma que espera la cabecera de la subida (E-1)."""
    return base64.b64encode(bytes.fromhex(sha256_hex)).decode("ascii")


def _ascii_seguro(nombre: str) -> str:
    """El nombre con todo carácter fuera de 0x20 a 0x7E, `"` y `\\` cambiado por `_`.

    Es la parte `filename=` de la disposición: una cabecera HTTP solo admite ASCII visible.
    """
    return "".join(
        "_" if not (0x20 <= ord(caracter) <= 0x7E) or caracter in '"\\' else caracter
        for caracter in nombre
    )


def _disposicion(disposicion: str, nombre_original: str) -> str:
    """`Content-Disposition` con el nombre en ASCII y, aparte, en UTF-8 codificado (RFC 6266)."""
    codificado = quote(nombre_original, safe="")
    return f"{disposicion}; filename=\"{_ascii_seguro(nombre_original)}\"; filename*=UTF-8''{codificado}"


def _sin_objeto(error: ClientError) -> bool:
    """Un `HEAD` sin objeto responde `404` sin cuerpo; un `GET`, `NoSuchKey`."""
    return str(error.response.get("Error", {}).get("Code", "")) in AUSENCIAS


class AlmacenS3:
    """Operaciones del almacén de objetos sobre S3, con el puerto `AlmacenObjetos` (ADR-016)."""

    def __init__(self, cliente: S3Client, firmante: S3Client, bucket: str) -> None:
        self._cliente = cliente
        self._firmante = firmante
        self._bucket = bucket

    def url_subida(
        self, clave: str, *, tamano_bytes: int, sha256_hex: str, vida: timedelta
    ) -> UrlFirmada:
        """URL de PUT con el tamaño y la suma firmados: otro cuerpo o tamaño se rechaza (RNF-19)."""
        suma = _suma_base64(sha256_hex)
        url = self._firmante.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self._bucket,
                "Key": clave,
                "ContentLength": tamano_bytes,
                "ChecksumSHA256": suma,
            },
            ExpiresIn=int(vida.total_seconds()),
            HttpMethod="PUT",
        )
        return UrlFirmada(url=url, cabeceras={CABECERA_SUMA: suma})

    def metadatos(self, clave: str) -> ObjetoAlmacenado | None:
        """Tamaño y suma del objeto. Sin objeto, `None`; sin suma guardada, `sha256_hex=None`."""
        try:
            cabeza = self._cliente.head_object(
                Bucket=self._bucket, Key=clave, ChecksumMode="ENABLED"
            )
        except ClientError as error:
            if _sin_objeto(error):
                return None
            raise
        suma = cabeza.get("ChecksumSHA256")
        return ObjetoAlmacenado(
            tamano_bytes=int(cabeza["ContentLength"]),
            sha256_hex=None if suma is None else base64.b64decode(suma).hex(),
        )

    def leer_rango(self, clave: str, inicio: int, fin: int) -> bytes:
        """Bytes `inicio` a `fin`, ambos inclusivos. Una clave sin objeto propaga el error.

        Un rango inválido se rechaza antes de llamar al almacén (RNF-06, PA-T59.14).
        """
        if inicio < 0 or fin < inicio:
            raise ValueError(f"Rango inválido: {inicio}-{fin}; se exige 0 <= inicio <= fin")
        respuesta = self._cliente.get_object(
            Bucket=self._bucket, Key=clave, Range=f"bytes={inicio}-{fin}"
        )
        return respuesta["Body"].read()

    def leer_todo(self, clave: str) -> bytes:
        """Contenido completo del objeto. Una clave sin objeto propaga el error."""
        respuesta = self._cliente.get_object(Bucket=self._bucket, Key=clave)
        return respuesta["Body"].read()

    def reescribir_tipo(self, clave: str, tipo_mime: str) -> None:
        """Copia el objeto sobre sí mismo con otro tipo. `REPLACE` conserva la suma (E-1, g1)."""
        self._cliente.copy_object(
            Bucket=self._bucket,
            Key=clave,
            CopySource={"Bucket": self._bucket, "Key": clave},
            MetadataDirective="REPLACE",
            ContentType=tipo_mime,
        )

    def url_lectura(
        self,
        clave: str,
        *,
        vida: timedelta,
        tipo_mime: str,
        nombre_original: str,
        disposicion: str,
    ) -> str:
        """URL de GET con el tipo y la disposición de descarga fijados en la respuesta."""
        return self._firmante.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self._bucket,
                "Key": clave,
                "ResponseContentType": tipo_mime,
                "ResponseContentDisposition": _disposicion(disposicion, nombre_original),
            },
            ExpiresIn=int(vida.total_seconds()),
        )


def crear_almacen_s3(
    *,
    endpoint: str | None,
    origen: str,
    bucket: str,
    clave_acceso: str,
    clave_secreta: str,
) -> AlmacenS3:
    """Construye el adaptador con dos clientes: el de servidor y el firmante (ver el módulo).

    Sin `endpoint`, los dos apuntan al origen. Los plazos de conexión y lectura acotan la espera
    de un hilo del pool de FastAPI, que las rutas `def` comparten; los reintentos son tres como
    máximo.
    """
    configuracion = Config(
        signature_version="s3v4",
        s3={"addressing_style": "path"},
        request_checksum_calculation="when_required",
        response_checksum_validation="when_required",
        connect_timeout=5,
        read_timeout=30,
        retries={"max_attempts": 3, "mode": "standard"},
    )

    def _crear(direccion: str) -> S3Client:
        return boto3.client(
            "s3",
            endpoint_url=direccion,
            region_name=REGION,
            aws_access_key_id=clave_acceso,
            aws_secret_access_key=clave_secreta,
            config=configuracion,
        )

    cliente = _crear(endpoint if endpoint is not None else origen)
    firmante = _crear(origen)
    return AlmacenS3(cliente, firmante, bucket)
