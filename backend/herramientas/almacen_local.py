"""Crea el bucket del almacén de objetos en el MinIO local (TKT-059, fila 1b, P-6).

Se invoca desde backend/ con:
uv run --env-file ../.env python -m herramientas.almacen_local

Lee cuatro variables: CIMENTA_ALMACEN_ORIGEN, CIMENTA_ALMACEN_BUCKET, CIMENTA_ALMACEN_CLAVE_ACCESO y
CIMENTA_ALMACEN_CLAVE_SECRETA. Solo actúa sobre un MinIO local: rehúsa cualquier origen cuyo host no sea
exactamente `localhost` o `127.0.0.1`. El CORS no lo fija esta herramienta: lo da
MINIO_API_CORS_ALLOW_ORIGIN en compose.almacen.yaml (E-5, caso c2). Ningún secreto se imprime.
"""

import os
import sys
from collections.abc import Mapping
from typing import TYPE_CHECKING, Final
from urllib.parse import urlsplit

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

VARIABLES_OBLIGATORIAS: Final = (
    "CIMENTA_ALMACEN_ORIGEN",
    "CIMENTA_ALMACEN_BUCKET",
    "CIMENTA_ALMACEN_CLAVE_ACCESO",
    "CIMENTA_ALMACEN_CLAVE_SECRETA",
)
HOSTS_LOCALES: Final = frozenset({"localhost", "127.0.0.1"})
REGION: Final = "us-east-1"
CODIGOS_NO_EXISTE: Final = frozenset({"404", "NoSuchBucket", "NotFound"})
CODIGOS_YA_EXISTE: Final = frozenset({"BucketAlreadyOwnedByYou", "BucketAlreadyExists"})


def _origen_local(origen: str) -> bool:
    """Cierto si el host del origen es exactamente `localhost` o `127.0.0.1`.

    `urlsplit` compara el host completo, así que `localhost.ejemplo.test` no pasa. Un origen que
    `urlsplit` no puede leer cuenta como no local. Se rechaza también lo ambiguo: esquema distinto
    de http o https, barra invertida en el origen o credenciales en el `netloc` (seguridad F001).
    """
    try:
        partes = urlsplit(origen)
        host = partes.hostname
    except ValueError:
        return False
    if partes.scheme not in {"http", "https"} or "\\" in origen or "@" in partes.netloc:
        return False
    return host in HOSTS_LOCALES


def _asegurar_bucket(cliente: "S3Client", bucket: str) -> None:
    """Crea el bucket solo si `head_bucket` responde que no existe. Idempotente: repetir la llamada no falla.

    Cualquier otro error del almacén se propaga al llamador, que lo traduce a código de salida.
    """
    try:
        cliente.head_bucket(Bucket=bucket)
        return
    except ClientError as error:
        if error.response["Error"]["Code"] not in CODIGOS_NO_EXISTE:
            raise
    try:
        cliente.create_bucket(Bucket=bucket)
    except ClientError as error:
        if error.response["Error"]["Code"] not in CODIGOS_YA_EXISTE:
            raise


def _cliente(origen: str, valores: Mapping[str, str]) -> "S3Client":
    """Cliente boto3 contra el MinIO local: path style, firma s3v4 y sin checksums automáticos (E-5)."""
    return boto3.client(
        "s3",
        endpoint_url=origen,
        region_name=REGION,
        aws_access_key_id=valores["CIMENTA_ALMACEN_CLAVE_ACCESO"],
        aws_secret_access_key=valores["CIMENTA_ALMACEN_CLAVE_SECRETA"],
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
    )


def _motivo(error: BotoCoreError | ClientError) -> str:
    """El código de error del almacén, o el nombre de la excepción de red. Nunca el mensaje completo."""
    if isinstance(error, ClientError):
        return str(error.response["Error"]["Code"])
    return type(error).__name__


def main(entorno: Mapping[str, str]) -> int:
    """Valida el entorno, niega cualquier origen no local y asegura el bucket.

    Devuelve 0 si el bucket existe al terminar; 2 si falta una variable o el origen no es local; 1 si
    el almacén responde con un error. Los mensajes van a stderr y nunca incluyen la clave secreta.
    """
    valores = {nombre: entorno.get(nombre, "").strip() for nombre in VARIABLES_OBLIGATORIAS}
    faltan = [nombre for nombre, valor in valores.items() if not valor]
    if faltan:
        print(
            f"Falta la variable {', '.join(faltan)}. Defínela en el entorno; "
            "las claves están en .env.example.",
            file=sys.stderr,
        )
        return 2
    origen = valores["CIMENTA_ALMACEN_ORIGEN"]
    if not _origen_local(origen):
        print(
            "Negado: CIMENTA_ALMACEN_ORIGEN no es localhost ni 127.0.0.1. Esta herramienta solo "
            "crea el bucket de un MinIO local. No se ha conectado.",
            file=sys.stderr,
        )
        return 2
    bucket = valores["CIMENTA_ALMACEN_BUCKET"]
    try:
        _asegurar_bucket(_cliente(origen, valores), bucket)
    except (BotoCoreError, ClientError) as error:
        print(
            f"No se pudo preparar el bucket {bucket} en el almacén local: {_motivo(error)}. "
            "No se muestra ningún secreto.",
            file=sys.stderr,
        )
        return 1
    print(f"Bucket {bucket} listo en el almacén local.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(os.environ))
