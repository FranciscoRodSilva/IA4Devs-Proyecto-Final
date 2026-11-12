"""E-5 (CA-14) · MinIO restringe el origen del CORS por bucket, o al menos por la variable global.

Imagen: pgsty/minio:RELEASE.2026-08-04T00-00-00Z.
Ejecución: uv run --python 3.14 --with "testcontainers[minio]" --with boto3 --with httpx python -I -X utf8 e5_cors.py
"""

import base64
import hashlib
import sys
import urllib.parse

import boto3
import httpx
from botocore.config import Config
from botocore.exceptions import ClientError
from testcontainers.community.minio import MinioContainer

IMAGEN = "pgsty/minio:RELEASE.2026-08-04T00-00-00Z"
CLAVE_ACCESO = "cimenta-test"
CLAVE_SECRETA = "solo-desarrollo-prueba-secreto"  # valor de prueba, contenedor desechable
BUCKET = "cimenta-prueba"
ORIGEN_SPA = "http://localhost:5173"
ORIGEN_OTRO = "http://otro.prueba.test"
REGLA_CORS = {
    "CORSRules": [
        {
            "AllowedOrigins": [ORIGEN_SPA],
            "AllowedMethods": ["PUT", "GET", "HEAD"],
            "AllowedHeaders": ["content-type", "x-amz-checksum-sha256"],
            "ExposeHeaders": ["ETag"],
            "MaxAgeSeconds": 600,
        }
    ]
}


def cliente(endpoint_url: str):
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        region_name="us-east-1",
        aws_access_key_id=CLAVE_ACCESO,
        aws_secret_access_key=CLAVE_SECRETA,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
            connect_timeout=5,
            read_timeout=30,
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    )


def preflight(origen: str, endpoint: str, clave: str = "obra/prueba-cors") -> dict:
    url = f"{endpoint}/{BUCKET}/{clave}"
    r = httpx.options(
        url,
        headers={
            "Origin": origen,
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "x-amz-checksum-sha256",
        },
    )
    allow = {k: v for k, v in r.headers.items() if k.lower().startswith("access-control-allow")}
    return {"status": r.status_code, "allow": allow}


def imprimir_preflight(titulo: str, endpoint: str) -> dict:
    print(f"\n== {titulo}")
    out = {}
    for origen in (ORIGEN_SPA, ORIGEN_OTRO):
        p = preflight(origen, endpoint)
        out[origen] = p
        print(f"  Origin={origen} -> HTTP {p['status']} · {p['allow']}")
    return out


def restringe(p: dict) -> bool:
    # httpx entrega las cabeceras en minúsculas: la búsqueda es insensible a mayúsculas.
    spa = p[ORIGEN_SPA]["allow"].get("access-control-allow-origin")
    otro = p[ORIGEN_OTRO]["allow"].get("access-control-allow-origin")
    return spa == ORIGEN_SPA and otro is None


def comprobar_put_firmado(cli, endpoint: str, origen_cabecera: str) -> str | None:
    data = b"%PDF-1.4 e5"
    sha = hashlib.sha256(data).hexdigest()
    b64 = base64.b64encode(bytes.fromhex(sha)).decode("ascii")
    url = cli.generate_presigned_url(
        "put_object",
        Params={"Bucket": BUCKET, "Key": "obra/prueba-cors-put", "ContentLength": len(data), "ChecksumSHA256": b64},
        ExpiresIn=900,
        HttpMethod="PUT",
    )
    r = httpx.put(url, content=data, headers={"Origin": origen_cabecera, "x-amz-checksum-sha256": b64})
    acao = r.headers.get("access-control-allow-origin")
    print(f"  PUT firmado con Origin={origen_cabecera} -> HTTP {r.status_code} · Access-Control-Allow-Origin={acao!r}")
    return acao


def fase_container(titulo: str, env: dict[str, str], aplicar_bucket_cors: bool) -> dict:
    contenedor = MinioContainer(IMAGEN, access_key=CLAVE_ACCESO, secret_key=CLAVE_SECRETA)
    for k, v in env.items():
        contenedor.with_env(k, v)
    contenedor.start()
    try:
        endpoint = f"http://{contenedor.get_config()['endpoint']}"
        print(f"\n######## {titulo} · endpoint={endpoint} · env={env}")
        cli = cliente(endpoint)
        cli.create_bucket(Bucket=BUCKET)
        resultado: dict = {}
        resultado["base_sin_configurar"] = imprimir_preflight("(baseline) preflight sin regla de bucket", endpoint)
        if aplicar_bucket_cors:
            print("\n== (a) put_bucket_cors con la regla de «CORS del almacén»")
            try:
                r = cli.put_bucket_cors(Bucket=BUCKET, CORSConfiguration=REGLA_CORS)
                print(f"  respuesta HTTP {r['ResponseMetadata']['HTTPStatusCode']}")
                resultado["a"] = "aceptado"
            except ClientError as e:
                code = e.response["Error"].get("Code")
                print(f"  ClientError code={code} status={e.response['ResponseMetadata'].get('HTTPStatusCode')}")
                resultado["a"] = f"error {code}"
            try:
                g = cli.get_bucket_cors(Bucket=BUCKET)
                print(f"  get_bucket_cors -> {g.get('CORSRules')}")
            except ClientError as e:
                print(f"  get_bucket_cors -> ClientError {e.response['Error'].get('Code')}")
            resultado["b"] = imprimir_preflight("(b) preflight tras (a)", endpoint)
        else:
            resultado["a"] = "no aplicado en esta fase"
        resultado["d_acao_spa"] = comprobar_put_firmado(cli, endpoint, ORIGEN_SPA)
        resultado["d_acao_otro"] = comprobar_put_firmado(cli, endpoint, ORIGEN_OTRO)
        return resultado
    finally:
        contenedor.stop()


def main() -> int:
    # Fase 1: sin variable global, con regla de bucket (a), preflight (b), PUT firmado (d).
    f1 = fase_container("FASE 1 · regla de bucket (a) y (b), sin MINIO_API_CORS_ALLOW_ORIGIN", {}, True)
    b_f1 = f1.get("b", {})
    restringe_bucket = bool(b_f1) and restringe(b_f1)
    print(f"\n== Veredicto fase 1: (a)={f1['a']} · (b) restringe por bucket = {restringe_bucket} · (d) ACAO SPA={f1['d_acao_spa']!r} · (d) ACAO otro={f1['d_acao_otro']!r}")

    if restringe_bucket:
        caso = "c1"
        print("CASO (c1): MinIO acepta put_bucket_cors y lo respeta en el preflight")
    else:
        # Fase 2: sin regla de bucket, con MINIO_API_CORS_ALLOW_ORIGIN.
        f2 = fase_container(
            "FASE 2 · sin regla de bucket, con MINIO_API_CORS_ALLOW_ORIGIN=http://localhost:5173",
            {"MINIO_API_CORS_ALLOW_ORIGIN": ORIGEN_SPA},
            False,
        )
        p2 = f2["base_sin_configurar"]
        restringe_global = restringe(p2)
        print(f"\n== Veredicto fase 2: restringe por variable global = {restringe_global} · (d) ACAO SPA={f2['d_acao_spa']!r} · (d) ACAO otro={f2['d_acao_otro']!r}")
        if restringe_global:
            caso = "c2"
            print("CASO (c2): MinIO responde NotImplemented o no aplica la regla de bucket, y respeta MINIO_API_CORS_ALLOW_ORIGIN")
        else:
            caso = "c3"
            print("CASO (c3): ninguno de los dos mecanismos restringe el origen")

    print(f"\n== RESUMEN E-5 · caso = {caso}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
