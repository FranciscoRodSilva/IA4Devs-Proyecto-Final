"""CORS del almacén de objetos (TKT-059, fila 1b): TC-54, con CA-14, contra MinIO real.

El CORS de las pruebas lo fija la variable MINIO_API_CORS_ALLOW_ORIGIN del contenedor, en la fixture
`contenedor_minio` (E-5, caso c2). Ninguna pieza de producción interviene aquí: la prueba fija el
comportamiento de MinIO con esa configuración, y M-20 demuestra que la prueba lo detecta.

Lo que se comprueba son las cabeceras `Access-Control-Allow-*` que el navegador exige para leer la
respuesta. CORS es una barrera del navegador: el servidor responde a un PUT firmado de cualquier origen
si la firma es válida. Por eso el PUT de otro origen se comprueba con `200` además de sin cabecera.
"""

import base64
import hashlib
import uuid
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

ORIGEN_AJENO = "http://otro.prueba.test"
CONTENIDO = b"contenido de prueba para el PUT firmado de TKT-059"
TIEMPO_DE_VIDA_URL = 300


def _sha256_base64(contenido: bytes) -> str:
    return base64.b64encode(hashlib.sha256(contenido).digest()).decode("ascii")


def _clave() -> str:
    return f"cors/{uuid.uuid4().hex}"


def _url_put_firmada(cliente: "S3Client", bucket: str, clave: str) -> str:
    """La URL que el navegador usaría para subir: `put_object` con la suma firmada, como en E-1."""
    return cliente.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": bucket,
            "Key": clave,
            "ContentLength": len(CONTENIDO),
            "ChecksumSHA256": _sha256_base64(CONTENIDO),
        },
        ExpiresIn=TIEMPO_DE_VIDA_URL,
        HttpMethod="PUT",
    )


def _preflight(url: str, origen: str) -> httpx.Response:
    """El `OPTIONS` que el navegador manda antes del PUT con cabecera de suma."""
    with httpx.Client(timeout=10) as cliente:
        return cliente.options(
            url,
            headers={
                "Origin": origen,
                "Access-Control-Request-Method": "PUT",
                "Access-Control-Request-Headers": "x-amz-checksum-sha256",
            },
        )


def test_tkt059_ca14_cors_solo_desde_la_spa(
    cliente_s3: "S3Client", bucket_de_pruebas: str, origen_spa: str
) -> None:
    """TKT-059 TC-54 · CA-14 — el preflight de un PUT firmado devuelve Allow-Origin solo a la SPA."""
    url = _url_put_firmada(cliente_s3, bucket_de_pruebas, _clave())

    desde_spa = _preflight(url, origen_spa)
    assert 200 <= desde_spa.status_code < 300, desde_spa.text
    assert desde_spa.headers.get("access-control-allow-origin") == origen_spa
    metodos = {
        m.strip().upper()
        for m in desde_spa.headers.get("access-control-allow-methods", "").split(",")
    }
    assert "PUT" in metodos, desde_spa.headers
    cabeceras = {
        c.strip().lower()
        for c in desde_spa.headers.get("access-control-allow-headers", "").split(",")
    }
    assert "x-amz-checksum-sha256" in cabeceras, desde_spa.headers

    desde_ajeno = _preflight(url, ORIGEN_AJENO)
    assert "access-control-allow-origin" not in desde_ajeno.headers, desde_ajeno.headers


def test_tkt059_ca14_cors_solo_desde_la_spa_en_el_put_firmado(
    cliente_s3: "S3Client", bucket_de_pruebas: str, origen_spa: str
) -> None:
    """TKT-059 TC-54 · CA-14 — el PUT firmado devuelve 200 con Allow-Origin para la SPA y sin esa cabecera para otro origen."""
    url = _url_put_firmada(cliente_s3, bucket_de_pruebas, _clave())
    cabeceras = {"x-amz-checksum-sha256": _sha256_base64(CONTENIDO)}

    with httpx.Client(timeout=10) as cliente:
        desde_spa = cliente.put(url, content=CONTENIDO, headers={**cabeceras, "Origin": origen_spa})
        assert desde_spa.status_code == 200, desde_spa.text
        assert desde_spa.headers.get("access-control-allow-origin") == origen_spa

        desde_ajeno = cliente.put(
            url, content=CONTENIDO, headers={**cabeceras, "Origin": ORIGEN_AJENO}
        )
        assert desde_ajeno.status_code == 200, desde_ajeno.text
        assert "access-control-allow-origin" not in desde_ajeno.headers, desde_ajeno.headers
