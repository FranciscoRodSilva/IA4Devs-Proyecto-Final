"""Herramienta del bucket local (TKT-059, fila 1b): TC-51, con CA-13.

Prueba `herramientas/almacen_local.py`: `main(entorno: Mapping[str, str]) -> int` devuelve 0, 1 o 2 según
lo que ocurre con el bucket.

- Lee de `entorno` CIMENTA_ALMACEN_ORIGEN, CIMENTA_ALMACEN_BUCKET, CIMENTA_ALMACEN_CLAVE_ACCESO y
  CIMENTA_ALMACEN_CLAVE_SECRETA. Ninguna otra variable es obligatoria (CIMENTA_SPA_ORIGEN no la
  necesita: el CORS de MinIO lo fija el contenedor, E-5 caso c2).
- Devuelve 0 cuando el bucket existe al terminar, esté creado o ya existiera.
- Devuelve 1 si el almacén responde con un error (clave rechazada, servidor inalcanzable): el mensaje va a
  stderr y no incluye ninguna clave.
- Devuelve 2 si falta una de las cuatro variables, o si el origen de CIMENTA_ALMACEN_ORIGEN no es un
  `http`/`https` cuyo host sea exactamente `localhost` o `127.0.0.1`, sin barra invertida ni credenciales
  embebidas (`@`) en la autoridad. El mensaje va a stderr, nombra la variable y nunca imprime la clave secreta.

El import va dentro de cada test, no arriba, para que un fallo sea de la prueba y no de la colección.
"""

import uuid
from typing import TYPE_CHECKING

import pytest
from botocore.exceptions import ClientError
from testcontainers.community.minio import MinioContainer

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

VARIABLES_OBLIGATORIAS = (
    "CIMENTA_ALMACEN_ORIGEN",
    "CIMENTA_ALMACEN_BUCKET",
    "CIMENTA_ALMACEN_CLAVE_ACCESO",
    "CIMENTA_ALMACEN_CLAVE_SECRETA",
)
ORIGENES_NO_LOCALES = (
    "https://almacen.ejemplo.test",
    "http://minio.interno:9000",
    "http://localhost.ejemplo.test:9000",
    # `urlsplit` lanza ValueError con el corchete sin cerrar: un origen ilegible cuenta como no local.
    "http://[::1",
    # El host real es el que sigue a la última arroba: aquí `almacen.ejemplo.test`, no `localhost`.
    "http://localhost:9000@almacen.ejemplo.test",
    # Barra invertida antes de la arroba: `urlsplit` da el host `localhost`, pero urllib3 conecta a
    # `evil.example`. Se rechaza lo ambiguo (seguridad F001).
    "http://evil.example\\@localhost:9000",
    # Credenciales embebidas en un host local: ambiguas, se rechazan (seguridad F001).
    "http://user@localhost:9000",
    # Esquema distinto de http/https con host local: solo lo rechaza el control del esquema.
    "ftp://localhost:9000",
    "file://127.0.0.1/x",
    # Barra invertida final sin arroba: urlsplit da el host `localhost`, solo la rechaza el control de `\`.
    "http://localhost:9000\\",
)


def _bucket_nuevo() -> str:
    """Un nombre que no existe en el contenedor compartido: la herramienta debe crearlo."""
    return f"cimenta-{uuid.uuid4().hex[:12]}"


def _entorno(contenedor: MinioContainer, cliente: "S3Client", bucket: str) -> dict[str, str]:
    """Las cuatro variables obligatorias apuntando al contenedor de prueba."""
    return {
        "CIMENTA_ALMACEN_ORIGEN": cliente.meta.endpoint_url,
        "CIMENTA_ALMACEN_BUCKET": bucket,
        "CIMENTA_ALMACEN_CLAVE_ACCESO": contenedor.access_key,
        "CIMENTA_ALMACEN_CLAVE_SECRETA": contenedor.secret_key,
    }


def _existe(cliente: "S3Client", bucket: str) -> bool:
    """`head_bucket` sin excepción es que existe; el `404` es que no; cualquier otro error se propaga."""
    try:
        cliente.head_bucket(Bucket=bucket)
    except ClientError as error:
        if error.response["Error"]["Code"] in ("404", "NoSuchBucket"):
            return False
        raise
    return True


def test_tkt059_herramienta_almacen_local(
    contenedor_minio: MinioContainer, cliente_s3: "S3Client"
) -> None:
    """TKT-059 TC-51 · CA-13 — la herramienta crea el bucket local y una segunda llamada no falla."""
    bucket = _bucket_nuevo()
    entorno = _entorno(contenedor_minio, cliente_s3, bucket)
    assert not _existe(cliente_s3, bucket), "precondición: el bucket no debe existir antes"

    from herramientas.almacen_local import main

    assert main(entorno) == 0
    assert _existe(cliente_s3, bucket)
    assert main(entorno) == 0, "una segunda llamada no debe fallar"
    assert _existe(cliente_s3, bucket)


@pytest.mark.parametrize("origen", ORIGENES_NO_LOCALES)
def test_tkt059_herramienta_almacen_local_rechaza_origen_no_local(
    origen: str,
    contenedor_minio: MinioContainer,
    cliente_s3: "S3Client",
    capsys: pytest.CaptureFixture[str],
) -> None:
    """TKT-059 TC-51 · CA-13 — un origen ilegible, con host ajeno o con barra invertida o credenciales embebidas termina con 2, nombra CIMENTA_ALMACEN_ORIGEN, dice Negado, no escribe nada y no filtra la clave secreta."""
    bucket = _bucket_nuevo()
    entorno = {**_entorno(contenedor_minio, cliente_s3, bucket), "CIMENTA_ALMACEN_ORIGEN": origen}

    from herramientas.almacen_local import main

    codigo = main(entorno)
    capturado = capsys.readouterr()

    assert codigo == 2
    assert "CIMENTA_ALMACEN_ORIGEN" in capturado.err
    assert "Negado" in capturado.err
    assert contenedor_minio.secret_key not in capturado.out + capturado.err
    assert not _existe(cliente_s3, bucket), "con un origen no local la herramienta no escribe nada"


@pytest.mark.parametrize("variable", VARIABLES_OBLIGATORIAS)
def test_tkt059_herramienta_almacen_local_rechaza_variable_ausente(
    variable: str,
    contenedor_minio: MinioContainer,
    cliente_s3: "S3Client",
    capsys: pytest.CaptureFixture[str],
) -> None:
    """TKT-059 TC-51 · CA-13 — con una variable obligatoria ausente termina con 2, nombra esa variable y no filtra la clave secreta."""
    entorno = _entorno(contenedor_minio, cliente_s3, _bucket_nuevo())
    del entorno[variable]

    from herramientas.almacen_local import main

    codigo = main(entorno)
    capturado = capsys.readouterr()

    assert codigo == 2
    assert variable in capturado.err
    assert contenedor_minio.secret_key not in capturado.out + capturado.err


CLAVE_INCORRECTA = "otra-clave-incorrecta"
ORIGEN_LOCAL_SIN_SERVIDOR = "http://127.0.0.1:1"


def test_tkt059_herramienta_almacen_local_error_del_almacen_devuelve_1(
    contenedor_minio: MinioContainer,
    cliente_s3: "S3Client",
    capsys: pytest.CaptureFixture[str],
) -> None:
    """TKT-059 TC-51 · CA-13 — con una clave secreta que el almacén rechaza termina con 1, dice que no pudo preparar el bucket, no filtra ninguna clave y no crea el bucket."""
    bucket = _bucket_nuevo()
    entorno = {
        **_entorno(contenedor_minio, cliente_s3, bucket),
        "CIMENTA_ALMACEN_CLAVE_SECRETA": CLAVE_INCORRECTA,
    }

    from herramientas.almacen_local import main

    codigo = main(entorno)
    capturado = capsys.readouterr()

    assert codigo == 1
    assert "No se pudo preparar el bucket" in capturado.err
    assert contenedor_minio.secret_key not in capturado.out + capturado.err
    assert CLAVE_INCORRECTA not in capturado.out + capturado.err
    assert not _existe(cliente_s3, bucket), "con la clave rechazada el bucket sigue sin existir"


def test_tkt059_herramienta_almacen_local_servidor_inalcanzable_devuelve_1(
    contenedor_minio: MinioContainer,
    cliente_s3: "S3Client",
    capsys: pytest.CaptureFixture[str],
) -> None:
    """TKT-059 TC-51 · CA-13 — con un origen local en el que no escucha ningún servidor termina con 1, dice que no pudo preparar el bucket y no filtra la clave secreta."""
    bucket = _bucket_nuevo()
    entorno = {
        **_entorno(contenedor_minio, cliente_s3, bucket),
        "CIMENTA_ALMACEN_ORIGEN": ORIGEN_LOCAL_SIN_SERVIDOR,
    }

    from herramientas.almacen_local import main

    codigo = main(entorno)
    capturado = capsys.readouterr()

    assert codigo == 1
    assert "No se pudo preparar el bucket" in capturado.err
    assert contenedor_minio.secret_key not in capturado.out + capturado.err
    assert not _existe(cliente_s3, bucket), (
        "sin servidor la herramienta no crea nada en el contenedor"
    )
