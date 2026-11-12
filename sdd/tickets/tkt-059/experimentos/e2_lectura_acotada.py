"""E-2 (PA-T59.14) · La comprobación estructural de un .xlsx grande cabe en lecturas por rango acotadas.

Libro: openpyxl mínimo + xl/media/relleno.bin de 26,000,000 bytes aleatorios, ZIP_STORED, añadido con zipfile modo "a".
Algoritmo: rama ZIP de «Detección del tipo por los bytes» (design.md), con get_object(Range=...), contando bytes.
Ejecución: uv run --python 3.14 --with "testcontainers[minio]" --with boto3 --with openpyxl --with defusedxml python -I -X utf8 e2_lectura_acotada.py
"""

import io
import os
import struct
import sys
import zipfile
import zlib

import boto3
import openpyxl
from botocore.config import Config
from defusedxml.ElementTree import fromstring
from testcontainers.community.minio import MinioContainer

IMAGEN = "pgsty/minio:RELEASE.2026-08-04T00-00-00Z"
CLAVE_ACCESO = "cimenta-test"
CLAVE_SECRETA = "solo-desarrollo-prueba-secreto"  # valor de prueba, contenedor desechable
BUCKET = "cimenta-prueba"
CLAVE = "obra/libro-26mb.xlsx"
TAMANO_RELLENO = 26_000_000
COTA_BYTES = 262144

CABECERA = 8192
COLA_ZIP = 65557
MAXIMO_DIRECTORIO = 1048576
MAXIMO_PARTE = 1048576
XLSX_PRINCIPAL = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"


def construir_libro() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"] = "concepto"
    ws["B1"] = "importe"
    ws["A2"] = "Muro tablaroca"
    ws["B2"] = "12000.00"
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    with zipfile.ZipFile(buf, "a", compression=zipfile.ZIP_STORED) as z:
        z.writestr("xl/media/relleno.bin", os.urandom(TAMANO_RELLENO))
    return buf.getvalue()


class LectorContado:
    def __init__(self, cli):
        self.cli = cli
        self.llamadas = []
        self.bytes_leidos = 0
        self.leer_todo_llamado = False

    def __call__(self, inicio: int, fin: int) -> bytes:
        r = self.cli.get_object(Bucket=BUCKET, Key=CLAVE, Range=f"bytes={inicio}-{fin}")
        datos = r["Body"].read()
        estado = r["ResponseMetadata"]["HTTPStatusCode"]
        self.llamadas.append((inicio, fin, estado, r.get("ContentRange"), len(datos)))
        self.bytes_leidos += len(datos)
        return datos


def detectar_zip_xlsx(leer, tamano: int) -> str:
    """Rama ZIP de «Detección del tipo» (design.md, sección de detección por bytes)."""
    cabecera = leer(0, min(tamano, CABECERA) - 1)
    if not cabecera.startswith(b"PK\x03\x04"):
        return "no-zip"
    cola = leer(max(0, tamano - COLA_ZIP), tamano - 1)
    pos = cola.rfind(b"PK\x05\x06")
    if pos < 0 or len(cola) - pos < 22:
        return "application/zip"
    (_, _, _, entradas, cd_tam, cd_pos, _) = struct.unpack("<HHHHIIH", cola[pos + 4 : pos + 22])
    print(f"  EOCD: entradas={entradas} cd_tam={cd_tam} cd_pos={cd_pos} (ZIP64 si 0xFFFF/0xFFFFFFFF)")
    if entradas == 0xFFFF or cd_tam == 0xFFFFFFFF or cd_pos == 0xFFFFFFFF or cd_tam > MAXIMO_DIRECTORIO:
        return "application/zip"
    directorio = leer(cd_pos, cd_pos + cd_tam - 1)
    off = 0
    entrada = None
    while off + 46 <= len(directorio) and directorio[off : off + 4] == b"PK\x01\x02":
        metodo, csize, _usize = struct.unpack("<HII", directorio[off + 10 : off + 10 + 2] + directorio[off + 20 : off + 28])
        nlen, elen, clen = struct.unpack("<HHH", directorio[off + 28 : off + 34])
        local_off = struct.unpack("<I", directorio[off + 42 : off + 46])[0]
        nombre = directorio[off + 46 : off + 46 + nlen]
        if nombre == b"[Content_Types].xml":
            entrada = (metodo, csize, local_off)
            break
        off += 46 + nlen + elen + clen
    if entrada is None:
        return "application/zip"
    metodo, csize, local_off = entrada
    if csize > MAXIMO_PARTE:
        return "application/zip"
    cab_local = leer(local_off, local_off + 29)
    if not cab_local.startswith(b"PK\x03\x04"):
        return "application/zip"
    nlen_l, elen_l = struct.unpack("<HH", cab_local[26:30])
    inicio_datos = local_off + 30 + nlen_l + elen_l
    datos = leer(inicio_datos, inicio_datos + csize - 1) if csize > 0 else b""
    if metodo == 8:
        parte = zlib.decompressobj(-15).decompress(datos, MAXIMO_PARTE + 1)
    elif metodo == 0:
        parte = datos
    else:
        return "application/zip"
    if len(parte) > MAXIMO_PARTE:
        return "application/zip"
    root = fromstring(parte, forbid_dtd=True)
    for el in root.iter():
        if el.tag.endswith("Override") and el.get("ContentType") == XLSX_PRINCIPAL:
            return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return "application/zip"


def main() -> int:
    libro = construir_libro()
    tamano = len(libro)
    print(f"[libro] tamano_bytes={tamano} (relleno {TAMANO_RELLENO} bytes, ZIP_STORED)")

    contenedor = MinioContainer(IMAGEN, access_key=CLAVE_ACCESO, secret_key=CLAVE_SECRETA)
    contenedor.start()
    try:
        origen = f"http://{contenedor.get_config()['endpoint']}"
        cli = boto3.client(
            "s3",
            endpoint_url=origen,
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
        cli.create_bucket(Bucket=BUCKET)
        cli.put_object(Bucket=BUCKET, Key=CLAVE, Body=libro)
        print(f"[subida] {origen}/{BUCKET}/{CLAVE}")

        lector = LectorContado(cli)
        tipo = detectar_zip_xlsx(lector, tamano)

        print("\n== Llamadas get_object(Range=...)")
        for inicio, fin, estado, rango_resp, n in lector.llamadas:
            pedido = fin - inicio + 1
            print(f"  bytes={inicio}-{fin} · pedidos={pedido} · recibidos={n} · HTTP {estado} · Content-Range={rango_resp}")
        todas_206 = all(e == 206 for _, _, e, _, _ in lector.llamadas)
        longitudes_ok = all(n == (fin - inicio + 1) for inicio, fin, _, _, n in lector.llamadas)

        print("\n== RESUMEN E-2")
        print(f"tipo detectado = {tipo}")
        print(f"llamadas = {len(lector.llamadas)} · todas 206 = {todas_206} · longitud pedida = recibida: {longitudes_ok}")
        print(f"bytes leidos = {lector.bytes_leidos} · cota = {COTA_BYTES} · cumple cota = {lector.bytes_leidos <= COTA_BYTES}")
        ok = tipo.endswith("sheet") and todas_206 and longitudes_ok and lector.bytes_leidos <= COTA_BYTES
        print(f"VEREDICTO E-2 = {'OK' if ok else 'FALLA'}")
        return 0 if ok else 1
    finally:
        contenedor.stop()


if __name__ == "__main__":
    sys.exit(main())
