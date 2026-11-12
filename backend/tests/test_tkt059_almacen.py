"""Puerto y adaptador del almacén de objetos (TKT-059, fila 5): TC-08, TC-08b, TC-21 y TC-33.

Contra MinIO real con testcontainers (fixtures de `conftest.py`), nunca contra un doble: una URL
prefirmada que no se firma, no caduca o no verifica la suma no lo demuestra ningún doble.

Los símbolos de producción (`puertos`, `almacen_s3`) se importan dentro del cuerpo de cada prueba
o de la fixture `almacen`, no a nivel de módulo: hasta que existan, el rojo es un
`ModuleNotFoundError` de la capa nueva y no un error de colección.

El espía de TC-08b envuelve los clientes de boto3 que `crear_almacen_s3` construye, sin cambiar lo
que devuelven: anota por qué dirección (`meta.endpoint_url`) sale cada llamada.
"""

import base64
import hashlib
import re
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, quote, unquote, urlsplit

import boto3
import httpx
import pytest
from botocore.exceptions import ClientError
from testcontainers.community.minio import MinioContainer

from cimenta.archivos.dominio.confirmacion import ObjetoAlmacenado

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

    from cimenta.archivos.infraestructura.almacen_s3 import AlmacenS3

ADAPTADOR = (
    Path(__file__).resolve().parents[1]
    / "cimenta"
    / "archivos"
    / "infraestructura"
    / "almacen_s3.py"
)

CONTENIDO = b"%PDF-1.4\n" + b"cimenta-TKT059-fila5-" * 200
VIDA_SUBIDA = timedelta(minutes=15)
VIDA_LECTURA = timedelta(minutes=5)
TIEMPO_DE_SONDEO = 15.0  # segundos, límite del sondeo de caducidad
MARGEN_DEL_SEGUNDO = 300_000  # microsegundos: se firma en la primera parte del segundo (ver abajo)


def _clave() -> str:
    """La clave que genera el alta: `obra_id/archivo_id`, sin el nombre original."""
    return f"{uuid.uuid4()}/{uuid.uuid4()}"


def _sha256_hex(contenido: bytes) -> str:
    return hashlib.sha256(contenido).hexdigest()


def _suma_base64(sha256_hex: str) -> str:
    """La cabecera `x-amz-checksum-sha256`: el SHA-256 en binario, en base64 (E-1)."""
    return base64.b64encode(bytes.fromhex(sha256_hex)).decode("ascii")


def _origen_de(url: str) -> str:
    """Esquema, host y puerto de una URL; lo que el navegador ve como origen."""
    partes = urlsplit(url)
    return f"{partes.scheme}://{partes.netloc}"


def _origen_del_contenedor(contenedor: MinioContainer) -> str:
    return f"http://{contenedor.get_container_host_ip()}:{contenedor.get_exposed_port(9000)}"


def _firmar_al_comienzo_del_segundo(firmar: Callable[[], str]) -> str:
    """Firma cuando el reloj va por la primera parte del segundo.

    `X-Amz-Date` tiene precisión de segundo. Con una vida de 1 s, una URL firmada en el último
    instante de un segundo caduca antes de su primer `GET`. Se espera ese comienzo consultando el
    reloj en bucle, sin `sleep`: la espera dura como mucho un segundo.
    """
    while datetime.now(UTC).microsecond >= MARGEN_DEL_SEGUNDO:
        pass
    return firmar()


class _ClienteEspiado:
    """Envuelve un cliente de boto3: anota (endpoint, método) de cada llamada y delega en el real."""

    def __init__(self, real: Any, llamadas: list[tuple[str, str]]) -> None:
        self._real = real
        self._llamadas = llamadas

    def __getattr__(self, nombre: str) -> Any:
        valor = getattr(self._real, nombre)
        if not callable(valor):
            return valor

        def _llamada(*args: Any, **kwargs: Any) -> Any:
            self._llamadas.append((self._real.meta.endpoint_url, nombre))
            return valor(*args, **kwargs)

        return _llamada


def _espiar_clientes(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[list[tuple[str, str]], list[str]]:
    """Sustituye `boto3.client` por una fábrica espía. Devuelve (llamadas, endpoints construidos).

    `monkeypatch` deshace el cambio al terminar la prueba.
    """
    original = boto3.client
    llamadas: list[tuple[str, str]] = []
    construidos: list[str] = []

    def _fabrica(*args: Any, **kwargs: Any) -> _ClienteEspiado:
        construidos.append(kwargs["endpoint_url"])
        return _ClienteEspiado(original(*args, **kwargs), llamadas)

    monkeypatch.setattr(boto3, "client", _fabrica)
    return llamadas, construidos


def _clientes_usados(llamadas: list[tuple[str, str]], desde: int) -> set[str]:
    """Las direcciones por las que salieron las llamadas a partir de la posición `desde`."""
    return {endpoint for endpoint, _ in llamadas[desde:]}


PROVEEDORES_PROHIBIDOS = ("minio", "r2", "cloudflare")


def _nombra_proveedor(texto: str, proveedor: str) -> bool:
    """True si `proveedor` aparece como palabra completa, sin distinguir mayúsculas.

    Por subcadena, «dominio» contiene «minio» y el adaptador fallaría sin nombrar ningún proveedor.
    """
    return re.search(rf"\b{re.escape(proveedor)}\b", texto, re.IGNORECASE) is not None


# ----------------------------------------------------------------------------- TC-08


def test_tkt059_ca02_el_destino_cambia_solo_por_endpoint(
    almacen: "AlmacenS3", cliente_s3: "S3Client", bucket_de_pruebas: str
) -> None:
    """TKT-059 TC-08 · CA-2 esc. 3 — con el endpoint del contenedor el puerto funciona de extremo a extremo.

    Subida con la URL firmada (200), metadatos, rango inclusivo, lectura completa, cambio de tipo que
    conserva la suma y URL de descarga. El adaptador no nombra ningún proveedor.
    """
    from cimenta.archivos.aplicacion.puertos import UrlFirmada

    clave = _clave()
    sha = _sha256_hex(CONTENIDO)

    subida = almacen.url_subida(
        clave, tamano_bytes=len(CONTENIDO), sha256_hex=sha, vida=VIDA_SUBIDA
    )
    assert isinstance(subida, UrlFirmada)
    assert subida.cabeceras == {"x-amz-checksum-sha256": _suma_base64(sha)}

    with httpx.Client(timeout=10) as cliente:
        respuesta = cliente.put(subida.url, content=CONTENIDO, headers=subida.cabeceras)
    assert respuesta.status_code == 200, respuesta.text

    assert almacen.metadatos(clave) == ObjetoAlmacenado(tamano_bytes=len(CONTENIDO), sha256_hex=sha)
    assert almacen.leer_rango(clave, 4, 9) == CONTENIDO[4:10]  # inclusivo: 6 bytes
    assert almacen.leer_todo(clave) == CONTENIDO

    almacen.reescribir_tipo(clave, "application/pdf")
    cabeceras = cliente_s3.head_object(Bucket=bucket_de_pruebas, Key=clave, ChecksumMode="ENABLED")
    assert cabeceras["ContentType"] == "application/pdf"
    # La copia con REPLACE conserva la suma: por eso `reescribir_tipo` no lleva ChecksumAlgorithm (E-1, g1).
    assert cabeceras["ChecksumSHA256"] == _suma_base64(sha)

    lectura = almacen.url_lectura(
        clave,
        vida=VIDA_LECTURA,
        tipo_mime="application/pdf",
        nombre_original="a.pdf",
        disposicion="attachment",
    )
    with httpx.Client(timeout=10) as cliente:
        descarga = cliente.get(lectura)
    assert descarga.status_code == 200, descarga.text
    assert descarga.content == CONTENIDO
    assert descarga.headers["content-type"] == "application/pdf"

    texto = ADAPTADOR.read_text(encoding="utf-8")
    for proveedor in PROVEEDORES_PROHIBIDOS:
        assert not _nombra_proveedor(texto, proveedor), (
            f"almacen_s3.py nombra el proveedor {proveedor!r}"
        )


def test_tkt059_ca02_control_del_comprobador_de_proveedor() -> None:
    """Control de TC-08 (no es escenario) · el comprobador señala MinIO, R2 y Cloudflare como palabras y no «dominio»."""
    assert _nombra_proveedor("el endpoint es MinIO en local", "minio")
    assert _nombra_proveedor("endpoint de R2 en producción", "r2")
    assert _nombra_proveedor("el origen pasa por Cloudflare", "cloudflare")
    assert not _nombra_proveedor(
        "from cimenta.archivos.dominio.confirmacion import ObjetoAlmacenado", "minio"
    )


# ----------------------------------------------------------------------------- TC-08b


def test_tkt059_ca02_las_url_llevan_el_origen_publico(
    monkeypatch: pytest.MonkeyPatch,
    contenedor_minio: MinioContainer,
    bucket_de_pruebas: str,
) -> None:
    """TKT-059 TC-08b · CA-2 esc. 4 — las URL llevan el origen público; el resto usa el endpoint interno.

    El contenedor responde por dos nombres: `127.0.0.1` es el endpoint (el de dentro) y `localhost` es
    el origen (el que ve el navegador). Las URL firmadas, de subida y de lectura, deben llevar el
    origen; los metadatos, la lectura, la copia y el rango, salir por el endpoint. M-21 lo rompe.
    """
    from cimenta.archivos.aplicacion.puertos import UrlFirmada
    from cimenta.archivos.infraestructura.almacen_s3 import crear_almacen_s3

    puerto = contenedor_minio.get_exposed_port(9000)
    endpoint = f"http://127.0.0.1:{puerto}"
    origen = f"http://localhost:{puerto}"
    llamadas, construidos = _espiar_clientes(monkeypatch)
    almacen = crear_almacen_s3(
        endpoint=endpoint,
        origen=origen,
        bucket=bucket_de_pruebas,
        clave_acceso=contenedor_minio.access_key,
        clave_secreta=contenedor_minio.secret_key,
    )
    assert set(construidos) == {endpoint, origen}

    clave = _clave()
    sha = _sha256_hex(CONTENIDO)

    desde = len(llamadas)
    subida = almacen.url_subida(
        clave, tamano_bytes=len(CONTENIDO), sha256_hex=sha, vida=VIDA_SUBIDA
    )
    assert isinstance(subida, UrlFirmada)
    assert _origen_de(subida.url) == origen
    assert _clientes_usados(llamadas, desde) == {origen}  # solo el firmante firma

    with httpx.Client(timeout=10) as cliente:
        respuesta = cliente.put(subida.url, content=CONTENIDO, headers=subida.cabeceras)
    assert respuesta.status_code == 200, respuesta.text

    desde = len(llamadas)
    assert almacen.metadatos(clave) == ObjetoAlmacenado(tamano_bytes=len(CONTENIDO), sha256_hex=sha)
    assert _clientes_usados(llamadas, desde) == {endpoint}

    desde = len(llamadas)
    assert almacen.leer_rango(clave, 0, 7) == CONTENIDO[:8]
    assert _clientes_usados(llamadas, desde) == {endpoint}

    desde = len(llamadas)
    assert almacen.leer_todo(clave) == CONTENIDO
    assert _clientes_usados(llamadas, desde) == {endpoint}

    desde = len(llamadas)
    almacen.reescribir_tipo(clave, "application/pdf")
    assert _clientes_usados(llamadas, desde) == {endpoint}

    desde = len(llamadas)
    lectura = almacen.url_lectura(
        clave,
        vida=VIDA_LECTURA,
        tipo_mime="application/pdf",
        nombre_original="a.pdf",
        disposicion="attachment",
    )
    assert _origen_de(lectura) == origen
    assert _clientes_usados(llamadas, desde) == {origen}

    with httpx.Client(timeout=10) as cliente:
        descarga = cliente.get(lectura)
    assert descarga.status_code == 200, descarga.text
    assert descarga.content == CONTENIDO


def test_tkt059_ca02_sin_endpoint_las_dos_direcciones_son_el_origen(
    monkeypatch: pytest.MonkeyPatch,
    contenedor_minio: MinioContainer,
    bucket_de_pruebas: str,
) -> None:
    """TKT-059 TC-08b · CA-2 esc. 4 — sin `endpoint`, los dos clientes apuntan al origen."""
    from cimenta.archivos.infraestructura.almacen_s3 import crear_almacen_s3

    origen = _origen_del_contenedor(contenedor_minio)
    llamadas, construidos = _espiar_clientes(monkeypatch)
    almacen = crear_almacen_s3(
        endpoint=None,
        origen=origen,
        bucket=bucket_de_pruebas,
        clave_acceso=contenedor_minio.access_key,
        clave_secreta=contenedor_minio.secret_key,
    )
    assert set(construidos) == {origen}

    assert almacen.metadatos(_clave()) is None
    assert _clientes_usados(llamadas, 0) == {origen}


# ----------------------------------------------------------------------------- TC-21


def test_tkt059_ca05_el_almacen_rechaza_la_subida_distinta(
    almacen: "AlmacenS3", cliente_s3: "S3Client", bucket_de_pruebas: str
) -> None:
    """TKT-059 TC-21 · CA-5 esc. 3 — un PUT con otro contenido del mismo tamaño responde 400 y no crea el objeto.

    E-1: la suma firmada no coincide con el cuerpo y MinIO responde `XAmzContentChecksumMismatch`.
    La fila del alta queda sin objeto, así que `metadatos` devuelve `None`.
    """
    clave = _clave()
    sha_firmado = _sha256_hex(CONTENIDO)
    otro = CONTENIDO.upper()  # mismo tamaño, otro contenido (las letras minúsculas cambian)
    assert len(otro) == len(CONTENIDO) and otro != CONTENIDO

    subida = almacen.url_subida(
        clave, tamano_bytes=len(CONTENIDO), sha256_hex=sha_firmado, vida=VIDA_SUBIDA
    )
    with httpx.Client(timeout=10) as cliente:
        respuesta = cliente.put(subida.url, content=otro, headers=subida.cabeceras)

    assert respuesta.status_code == 400, respuesta.text
    assert "XAmzContentChecksumMismatch" in respuesta.text
    assert almacen.metadatos(clave) is None
    with pytest.raises(ClientError) as error:
        cliente_s3.head_object(Bucket=bucket_de_pruebas, Key=clave)
    assert error.value.response["ResponseMetadata"]["HTTPStatusCode"] == 404


def test_tkt059_ca05_el_almacen_rechaza_una_suma_distinta_de_la_firmada(
    almacen: "AlmacenS3", cliente_s3: "S3Client", bucket_de_pruebas: str
) -> None:
    """TKT-059 TC-21 · CA-5 esc. 3 — un PUT con una suma coherente con su cuerpo, pero distinta de la firmada, responde 403.

    Es el hueco que deja el test anterior: allí la cabecera lleva la suma firmada y el cuerpo no la
    cumple, y MinIO rechaza por el cuerpo aunque la URL no firmara la suma. Aquí el cliente que
    sube miente de forma coherente: manda otro cuerpo del mismo tamaño y la suma de ese cuerpo. Solo
    la firma lo detiene, y solo si `ChecksumSHA256` va en `Params` de `url_subida`
    (`x-amz-checksum-sha256` pasa a la lista de cabeceras firmadas). Sin ella, MinIO acepta el PUT
    con 200 y el objeto queda guardado con un contenido que nadie firmó.
    """
    clave = _clave()
    sha_firmado = _sha256_hex(CONTENIDO)
    otro = CONTENIDO.upper()  # mismo tamaño, otro contenido
    assert len(otro) == len(CONTENIDO) and otro != CONTENIDO

    subida = almacen.url_subida(
        clave, tamano_bytes=len(CONTENIDO), sha256_hex=sha_firmado, vida=VIDA_SUBIDA
    )
    cabeceras_coherentes = {"x-amz-checksum-sha256": _suma_base64(_sha256_hex(otro))}
    assert cabeceras_coherentes != subida.cabeceras
    with httpx.Client(timeout=10) as cliente:
        respuesta = cliente.put(subida.url, content=otro, headers=cabeceras_coherentes)

    assert respuesta.status_code == 403, respuesta.text
    assert "SignatureDoesNotMatch" in respuesta.text
    assert almacen.metadatos(clave) is None
    with pytest.raises(ClientError) as error:
        cliente_s3.head_object(Bucket=bucket_de_pruebas, Key=clave)
    assert error.value.response["ResponseMetadata"]["HTTPStatusCode"] == 404


def test_tkt059_ca05_el_almacen_rechaza_la_subida_de_otro_tamano(
    almacen: "AlmacenS3", cliente_s3: "S3Client", bucket_de_pruebas: str
) -> None:
    """TKT-059 TC-21 · CA-5 esc. 3 — un PUT de otro tamaño que el firmado responde 403 y no crea el objeto.

    E-1 (d): el tamaño va firmado, así que la firma no coincide (`SignatureDoesNotMatch`).
    """
    clave = _clave()
    sha_firmado = _sha256_hex(CONTENIDO)
    mas_largo = CONTENIDO + b"X"

    subida = almacen.url_subida(
        clave, tamano_bytes=len(CONTENIDO), sha256_hex=sha_firmado, vida=VIDA_SUBIDA
    )
    with httpx.Client(timeout=10) as cliente:
        respuesta = cliente.put(subida.url, content=mas_largo, headers=subida.cabeceras)

    assert respuesta.status_code == 403, respuesta.text
    assert "SignatureDoesNotMatch" in respuesta.text
    assert almacen.metadatos(clave) is None
    with pytest.raises(ClientError) as error:
        cliente_s3.head_object(Bucket=bucket_de_pruebas, Key=clave)
    assert error.value.response["ResponseMetadata"]["HTTPStatusCode"] == 404


# ----------------------------------------------------------------------------- TC-33


def test_tkt059_ca08_la_url_caduca(
    almacen: "AlmacenS3", cliente_s3: "S3Client", bucket_de_pruebas: str
) -> None:
    """TKT-059 TC-33 · CA-8 esc. 3 — la URL de lectura de vida 1 s responde 200 y después 403.

    El sondeo tiene límite de 15 s y no duerme: vuelve a pedir la URL hasta que MinIO la rechaza.
    Sin `esperar_hasta` en `conftest.py`, el sondeo vive aquí.
    """
    clave = _clave()
    cliente_s3.put_object(Bucket=bucket_de_pruebas, Key=clave, Body=CONTENIDO)

    url = _firmar_al_comienzo_del_segundo(
        lambda: almacen.url_lectura(
            clave,
            vida=timedelta(seconds=1),
            tipo_mime="application/pdf",
            nombre_original="a.pdf",
            disposicion="attachment",
        )
    )

    limite = datetime.now(UTC).timestamp() + TIEMPO_DE_SONDEO
    with httpx.Client(timeout=10) as cliente:
        primero = cliente.get(url)
        assert primero.status_code == 200, primero.text
        assert primero.content == CONTENIDO

        while True:
            respuesta = cliente.get(url)
            if respuesta.status_code == 403:
                break
            assert respuesta.status_code == 200, respuesta.text
            if datetime.now(UTC).timestamp() >= limite:
                pytest.fail(f"La URL de 1 s seguía dando 200 tras {TIEMPO_DE_SONDEO:.0f} s")

    assert respuesta.content != CONTENIDO
    assert b"expired" in respuesta.content.lower() or b"AccessDenied" in respuesta.content


def test_tkt059_ca08_la_disposicion_neutraliza_nombres_hostiles(almacen: "AlmacenS3") -> None:
    """TKT-059 CA-8 · RNF-06 — un nombre con comillas, `\\r\\n` y no ASCII no inyecta cabeceras en `Content-Disposition`.

    Se decodifica `response-content-disposition` de la URL que devuelve `url_lectura`, y no se importa
    `_disposicion` (privada): el contrato es lo que el navegador recibirá, no la forma de la función.
    El `filename=` solo lleva ASCII visible sin `"` ni saltos de línea; el nombre completo viaja
    aparte, percent-encoded, en `filename*=UTF-8''` (RFC 6266). Sin `_ascii_seguro`, el nombre
    cierra la comilla y deja pasar `\\r\\n` y un `Set-Cookie`.
    """
    nombre = 'a"\r\nSet-Cookie: xñ.png'
    url = almacen.url_lectura(
        _clave(),
        vida=VIDA_LECTURA,
        tipo_mime="image/png",
        nombre_original=nombre,
        disposicion="attachment",
    )

    valores = parse_qs(urlsplit(url).query)["response-content-disposition"]
    assert len(valores) == 1
    cabecera = valores[0]

    assert "\r" not in cabecera and "\n" not in cabecera
    assert cabecera.count('"') == 2  # solo las dos comillas que delimitan filename=
    partes = re.fullmatch(r"attachment; filename=\"([^\"]*)\"; filename\*=UTF-8''(\S*)", cabecera)
    assert partes is not None, cabecera
    nombre_ascii, nombre_codificado = partes.groups()
    assert nombre_ascii.isascii() and nombre_ascii.isprintable()
    assert nombre_ascii == "a___Set-Cookie: x_.png"
    assert nombre_codificado == quote(nombre, safe="")
    assert unquote(nombre_codificado) == nombre


# ----------------------------------------------------------------------------- rechazos del puerto


def test_tkt059_ca02_metadatos_de_objeto_inexistente_es_none(almacen: "AlmacenS3") -> None:
    """TKT-059 · puerto `metadatos` — una clave sin objeto devuelve `None`, no un error (`NoSuchKey` o `NotFound` se traducen)."""
    assert almacen.metadatos(_clave()) is None


def test_tkt059_ca02_leer_rango_de_objeto_inexistente_propaga_el_error_del_almacen(
    almacen: "AlmacenS3",
) -> None:
    """TKT-059 · puerto `leer_rango` — una clave sin objeto propaga `botocore.ClientError` con `NoSuchKey` (404).

    Decisión de contrato: el puerto no traduce la ausencia en lectura; quien llama (el lector del
    ejecutor, TC-41) decide qué hacer con el error.
    """
    with pytest.raises(ClientError) as error:
        almacen.leer_rango(_clave(), 0, 9)
    assert error.value.response["Error"]["Code"] == "NoSuchKey"
    assert error.value.response["ResponseMetadata"]["HTTPStatusCode"] == 404


def test_tkt059_ca02_leer_todo_de_objeto_inexistente_propaga_el_error_del_almacen(
    almacen: "AlmacenS3",
) -> None:
    """TKT-059 · puerto `leer_todo` — una clave sin objeto propaga `botocore.ClientError` con `NoSuchKey` (404)."""
    with pytest.raises(ClientError) as error:
        almacen.leer_todo(_clave())
    assert error.value.response["Error"]["Code"] == "NoSuchKey"
    assert error.value.response["ResponseMetadata"]["HTTPStatusCode"] == 404


# ----------------------------------------------------------------------------- revisión ciclo 1


@pytest.mark.parametrize(
    ("inicio", "fin"),
    [
        pytest.param(-1, 3, id="inicio-negativo"),
        pytest.param(5, 3, id="inicio-mayor-que-fin"),
        pytest.param(0, -1, id="fin-negativo"),
    ],
)
def test_tkt059_ca02_leer_rango_invalido_se_rechaza_sin_leer(
    monkeypatch: pytest.MonkeyPatch,
    contenedor_minio: MinioContainer,
    bucket_de_pruebas: str,
    cliente_s3: "S3Client",
    inicio: int,
    fin: int,
) -> None:
    """TKT-059 · puerto `leer_rango` — un rango negativo o invertido lanza `ValueError` y no descarga nada.

    Con `Range: bytes=-1-3` o `bytes=5-3`, que la especificación HTTP manda ignorar, MinIO devuelve
    el objeto entero: el puerto lo convertiría en una descarga completa que el detector, por
    diseño, no hace nunca. El espía comprueba que ni un `get_object` sale hacia el almacén.
    """
    from cimenta.archivos.infraestructura.almacen_s3 import crear_almacen_s3

    clave = _clave()
    cliente_s3.put_object(Bucket=bucket_de_pruebas, Key=clave, Body=CONTENIDO)
    llamadas, _ = _espiar_clientes(monkeypatch)
    almacen = crear_almacen_s3(
        endpoint=None,
        origen=_origen_del_contenedor(contenedor_minio),
        bucket=bucket_de_pruebas,
        clave_acceso=contenedor_minio.access_key,
        clave_secreta=contenedor_minio.secret_key,
    )

    with pytest.raises(ValueError):
        almacen.leer_rango(clave, inicio, fin)

    assert [metodo for _, metodo in llamadas if metodo == "get_object"] == []


def test_tkt059_ca02_leer_rango_de_un_solo_byte_es_valido(
    almacen: "AlmacenS3", cliente_s3: "S3Client", bucket_de_pruebas: str
) -> None:
    """TKT-059 · puerto `leer_rango` — el rango `inicio == fin` es válido y devuelve un byte (frontera de la validación)."""
    clave = _clave()
    cliente_s3.put_object(Bucket=bucket_de_pruebas, Key=clave, Body=CONTENIDO)

    assert almacen.leer_rango(clave, 0, 0) == CONTENIDO[:1]
    assert almacen.leer_rango(clave, 3, 3) == CONTENIDO[3:4]


def test_tkt059_ca02_metadatos_propaga_el_error_que_no_es_ausencia(
    contenedor_minio: MinioContainer, bucket_de_pruebas: str
) -> None:
    """TKT-059 · puerto `metadatos` — un `403` (credenciales inválidas) propaga `ClientError`, no se confunde con «no existe».

    Solo `404`, `NoSuchKey` y `NotFound` significan «sin objeto» y devuelven `None`. Si el almacén
    rechaza al servidor, tratarlo como ausencia haría que el alta de un archivo diera por perdido
    un objeto que sí existe.
    """
    from cimenta.archivos.infraestructura.almacen_s3 import crear_almacen_s3

    almacen = crear_almacen_s3(
        endpoint=None,
        origen=_origen_del_contenedor(contenedor_minio),
        bucket=bucket_de_pruebas,
        clave_acceso=contenedor_minio.access_key,
        clave_secreta="una-clave-secreta-incorrecta",
    )

    with pytest.raises(ClientError) as error:
        almacen.metadatos(_clave())

    assert error.value.response["ResponseMetadata"]["HTTPStatusCode"] == 403
