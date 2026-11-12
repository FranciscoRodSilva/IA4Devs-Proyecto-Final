"""E-1 (PA-T59.6) · MinIO verifica la suma firmada y la devuelve.

Imagen: pgsty/minio:RELEASE.2026-08-04T00-00-00Z (decisión de la persona dueña, sustituye minio/minio).
Ejecución: uv run --python 3.14 --with "testcontainers[minio]" --with boto3 --with httpx python -I e1_suma_firmada.py
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
CABECERA_SUMA = "x-amz-checksum-sha256"


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


def b64_de_hex(sha_hex: str) -> str:
    return base64.b64encode(bytes.fromhex(sha_hex)).decode("ascii")


def cabeceras_firmadas(url: str) -> list[str]:
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
    return query.get("X-Amz-SignedHeaders", [""])[0].split(";")


def resumen(r: httpx.Response) -> str:
    cuerpo = r.text[:300].replace("\n", " ")
    return f"HTTP {r.status_code} · ETag={r.headers.get('etag')} · x-amz-checksum-sha256={r.headers.get('x-amz-checksum-sha256')} · cuerpo={cuerpo!r}"


def head_estado(cli, clave: str) -> str:
    try:
        r = cli.head_object(Bucket=BUCKET, Key=clave, ChecksumMode="ENABLED")
        return f"existe · ChecksumSHA256={r.get('ChecksumSHA256')} · ContentType={r.get('ContentType')} · ContentLength={r.get('ContentLength')}"
    except ClientError as e:
        return f"ClientError code={e.response['Error'].get('Code')} status={e.response['ResponseMetadata'].get('HTTPStatusCode')}"


def main() -> int:
    contenedor = MinioContainer(IMAGEN, access_key=CLAVE_ACCESO, secret_key=CLAVE_SECRETA)
    contenedor.start()
    try:
        cfg = contenedor.get_config()
        origen = f"http://{cfg['endpoint']}"
        print(f"[contenedor] imagen={IMAGEN} endpoint={origen}")
        cli = cliente(origen)
        cli.create_bucket(Bucket=BUCKET)

        data1 = b"%PDF-1.4\n" + (b"cimenta-E1-" * 400)  # contenido correcto
        data2 = b"%PDF-1.4\n" + (b"CIMENTA-E1-" * 400)  # mismo tamaño, otro contenido
        data3 = data1 + b"X"                            # otro tamaño
        assert len(data1) == len(data2) and len(data3) != len(data1)
        n1 = len(data1)
        sha1 = hashlib.sha256(data1).hexdigest()
        b64_1 = b64_de_hex(sha1)
        print(f"[datos] tamano_bytes={n1} sha256={sha1} b64={b64_1}")

        def firmar_put(clave: str, tamano: int, b64: str) -> str:
            return cli.generate_presigned_url(
                "put_object",
                Params={"Bucket": BUCKET, "Key": clave, "ContentLength": tamano, "ChecksumSHA256": b64},
                ExpiresIn=900,
                HttpMethod="PUT",
            )

        # (a) URL firmada
        k1 = "obra/prueba-1"
        url_a = firmar_put(k1, n1, b64_1)
        firmadas = cabeceras_firmadas(url_a)
        query_keys = sorted(urllib.parse.parse_qs(urllib.parse.urlsplit(url_a).query).keys())
        print("\n== (a) URL firmada put_object")
        print(f"URL: {url_a}")
        print(f"X-Amz-SignedHeaders = {firmadas}")
        print(f"Claves de la cadena de consulta = {query_keys}")
        suma_firmada = CABECERA_SUMA in firmadas
        print(f"¿{CABECERA_SUMA} en X-Amz-SignedHeaders? {suma_firmada}")
        print(f"¿{CABECERA_SUMA} en la cadena de consulta? {CABECERA_SUMA in query_keys or 'X-Amz-Checksum-Sha256' in query_keys}")

        cabeceras_cliente = {CABECERA_SUMA: b64_1} if suma_firmada else {}
        print(f"(b) cabeceras que debe llevar el cliente = {cabeceras_cliente}")

        # (b) contenido correcto
        r_b = httpx.put(url_a, content=data1, headers=cabeceras_cliente)
        print("\n== (b) PUT contenido correcto con cabecera")
        print(resumen(r_b))

        # (c) otra clave firmada igual, otro contenido del mismo tamaño
        k2 = "obra/prueba-2"
        url_c = firmar_put(k2, n1, b64_1)
        r_c = httpx.put(url_c, content=data2, headers=cabeceras_cliente)
        print("\n== (c) PUT a clave firmada igual, otro contenido del mismo tamaño")
        print(resumen(r_c))
        print(f"head_object({k2}) -> {head_estado(cli, k2)}")

        # (d) otro tamaño
        k3 = "obra/prueba-3"
        url_d = firmar_put(k3, n1, b64_1)
        r_d = httpx.put(url_d, content=data3, headers=cabeceras_cliente)
        print("\n== (d) PUT de contenido de otro tamaño")
        print(resumen(r_d))
        print(f"head_object({k3}) -> {head_estado(cli, k3)}")

        # (e) contenido correcto sin la cabecera
        ke = "obra/prueba-e"
        url_e = firmar_put(ke, n1, b64_1)
        r_e = httpx.put(url_e, content=data1)
        print("\n== (e) PUT contenido correcto SIN la cabecera (no condiciona nada)")
        print(resumen(r_e))
        print(f"head_object({ke}) -> {head_estado(cli, ke)}")

        # (f) tras (b)
        print("\n== (f) head_object(ChecksumMode=ENABLED) tras (b)")
        f_resp = cli.head_object(Bucket=BUCKET, Key=k1, ChecksumMode="ENABLED")
        suma_f = f_resp.get("ChecksumSHA256")
        print(f"ChecksumSHA256 = {suma_f}  · esperado {b64_1}  · coincide: {suma_f == b64_1}")
        print(f"ContentType = {f_resp.get('ContentType')} · ContentLength = {f_resp.get('ContentLength')}")

        # (g) copy_object con REPLACE y otro ContentType sobre la misma clave
        print("\n== (g) copy_object MetadataDirective=REPLACE, ContentType=application/pdf (sobre la misma clave)")
        cli.copy_object(
            Bucket=BUCKET,
            Key=k1,
            CopySource={"Bucket": BUCKET, "Key": k1},
            MetadataDirective="REPLACE",
            ContentType="application/pdf",
        )
        f_g = cli.head_object(Bucket=BUCKET, Key=k1, ChecksumMode="ENABLED")
        suma_g = f_g.get("ChecksumSHA256")
        print(f"tras copia: ChecksumSHA256 = {suma_g} · ContentType = {f_g.get('ContentType')}")
        if suma_g == b64_1:
            caso = "g1"
            print("RESULTADO (g1): la suma se conserva en la copia con REPLACE")
        else:
            print("La suma desaparece con REPLACE; se prueba ChecksumAlgorithm=SHA256 en otro objeto subido como (b)")
            kg2 = "obra/prueba-g2"
            url_g2 = firmar_put(kg2, n1, b64_1)
            r_g2 = httpx.put(url_g2, content=data1, headers=cabeceras_cliente)
            print(f"subida previa (b-style) de {kg2}: {resumen(r_g2)}")
            cli.copy_object(
                Bucket=BUCKET,
                Key=kg2,
                CopySource={"Bucket": BUCKET, "Key": kg2},
                MetadataDirective="REPLACE",
                ContentType="application/pdf",
                ChecksumAlgorithm="SHA256",
            )
            f_g2 = cli.head_object(Bucket=BUCKET, Key=kg2, ChecksumMode="ENABLED")
            print(f"tras copia con ChecksumAlgorithm=SHA256: ChecksumSHA256 = {f_g2.get('ChecksumSHA256')} · ContentType = {f_g2.get('ContentType')}")
            if f_g2.get("ChecksumSHA256") == b64_1:
                caso = "g2"
                print("RESULTADO (g2): la suma se pierde con REPLACE y se recupera con ChecksumAlgorithm=SHA256 (sobre el mismo contenido)")
            else:
                caso = "g3"
                print("RESULTADO (g3): la suma no se recupera con ninguna de las dos copias")

        # (h) GET prefirmado con disposición y tipo
        print("\n== (h) GET prefirmado con ResponseContentDisposition y ResponseContentType")
        url_h = cli.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": BUCKET,
                "Key": k1,
                "ResponseContentDisposition": 'attachment; filename="a.pdf"',
                "ResponseContentType": "application/pdf",
            },
            ExpiresIn=300,
        )
        r_h = httpx.get(url_h)
        print(f"HTTP {r_h.status_code} · Content-Disposition={r_h.headers.get('content-disposition')!r} · Content-Type={r_h.headers.get('content-type')!r} · cuerpo_coincide={r_h.content == data1}")

        print("\n== RESUMEN E-1")
        print(f"a) cabeceras firmadas: {firmadas}")
        print(f"b) cabeceras que debe llevar el cliente: {cabeceras_cliente}")
        print(f"c) (b)={r_b.status_code} (c)={r_c.status_code} (d)={r_d.status_code} (e)={r_e.status_code} "
              f"(f)={'ChecksumSHA256==b64' if suma_f == b64_1 else 'SIN SUMA'} "
              f"(g)={caso} (h)={r_h.status_code} con CD={r_h.headers.get('content-disposition')!r}")
        print(f"d) caso (g): {caso}")
        return 0
    finally:
        contenedor.stop()


if __name__ == "__main__":
    sys.exit(main())
