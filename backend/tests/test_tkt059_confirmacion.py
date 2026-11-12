"""Confirmación de un archivo por la API (TKT-059, fila 12a): TC-14 a TC-17.

`POST /api/v1/archivos/{archivo_id}/confirmacion` es la única ruta de `archivos` que muta. Comprueba el
objeto **realmente almacenado** (tamaño y suma por metadatos, tipo por lecturas de rango acotadas), lo
reescribe con su tipo real, pasa la fila a `DISPONIBLE` y asienta `CONFIRMAR` en la misma transacción.

PostgreSQL y MinIO reales con testcontainers: el esquema sale de `alembic upgrade head`, las escrituras
van con el rol de aplicación y la subida es un `PUT` real por la URL prefirmada. Las altas y las subidas
se hacen **dentro** del bloque `with TestClient(...)`, nunca antes (preámbulo del plan de pruebas). Ningún
`sleep`.

Esta suite no tiene `test_hdu001_esc24_…`: ese escenario es de TKT-018 (aviso del diseño). Los del camino
feliz se llaman `test_tkt059_…`.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, get_args

import pytest
from fastapi import FastAPI
from sqlalchemy import Engine

from cimenta.archivos.api.esquemas import Archivo
from cimenta.archivos.aplicacion.alta import TIPOS_DE_REFERENCIA
from herramientas.soporte_tkt017_api import (
    CABECERA_CORRELACION,
    NOMBRE_DEL_DIRECTOR,
    borrador,
    validar_contra,
)
from herramientas.soporte_tkt059 import (
    NOMBRE_DEL_LIBRO,
    TIPO_XLSX,
    TOPE_DE_LECTURA_POR_RANGO,
    AlmacenContador,
    abrir_sesion_del_director,
    asientos_del_archivo,
    cliente_https,
    confirmar_por_http,
    crear_aplicacion_de_archivos,
    dar_de_alta,
    fila_de_archivo,
    libro_con_relleno_de_26_mb,
    libro_de_presupuesto,
    sembrar_director,
    subir_objeto,
)

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta.
    from conftest import LibroCatalogo, RelojDePrueba, SembrarUsuario
    from mypy_boto3_s3 import S3Client

    from cimenta.archivos.infraestructura.almacen_s3 import AlmacenS3

CLAVES_DEL_ASIENTO = {
    "hash_sha256",
    "tamano_bytes",
    "tipo_mime",
    "referencia_tipo",
    "referencia_id",
}


def _tipo_del_objeto(cliente_s3: S3Client, bucket: str, clave: str) -> str:
    return cliente_s3.head_object(Bucket=bucket, Key=clave)["ContentType"]


def _instante(texto: str) -> datetime:
    return datetime.fromisoformat(texto)


# --------------------------------------------------------------------------- TC-14


def test_tkt059_ca04_confirmar_un_xlsx(
    aplicacion_archivos: FastAPI,
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    libro_catalogo: LibroCatalogo,
    cliente_s3: S3Client,
    bucket_de_pruebas: str,
) -> None:
    """TC-14 · CA-4 esc. 1 · RNF-19 — quien subió un `.xlsx` lo confirma: `200`, fila `DISPONIBLE` y asiento `CONFIRMAR`.

    Alta, `PUT` del libro con `Content-Type: application/octet-stream` y confirmación. El cuerpo valida
    contra `Archivo` del borrador, tiene exactamente sus propiedades y ninguna `clave_objeto`. La fila queda
    `DISPONIBLE` con el tipo `.xlsx` leído de los bytes y `confirmado_en` igual al reloj; el objeto, que se
    subió como `application/octet-stream`, ahora tiene el tipo `.xlsx`. La bitácora recibe un solo
    `CONFIRMAR` de `archivo`, con la obra, a nombre de quien confirmó y con el hash, el tamaño, el tipo y la
    referencia en `datos_despues` (el escenario 24 de HDU-001 es de TKT-018).
    """
    usuario_id = sembrar_director(sembrar_usuario)
    contenido = libro_de_presupuesto(libro_catalogo)

    with cliente_https(aplicacion_archivos) as cliente:
        sesion_id = abrir_sesion_del_director(cliente)
        archivo = dar_de_alta(
            aplicacion_archivos, motor_aplicacion, usuario_id=usuario_id, contenido=contenido
        )
        subir_objeto(archivo)
        assert _tipo_del_objeto(cliente_s3, bucket_de_pruebas, archivo.clave) == (
            "application/octet-stream"
        ), "El objeto debe subir como application/octet-stream: el tipo lo fija la confirmación"
        assert fila_de_archivo(motor_aplicacion, archivo.archivo_id)["estado"] == "PENDIENTE"

        respuesta = confirmar_por_http(cliente, sesion_id, archivo.archivo_id)

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.headers["content-type"].startswith("application/json")
    cuerpo = respuesta.json()
    validar_contra("Archivo", cuerpo)
    assert set(cuerpo) == set(borrador()["components"]["schemas"]["Archivo"]["properties"])
    assert "clave_objeto" not in cuerpo
    assert {clave: valor for clave, valor in cuerpo.items() if not clave.endswith("_en")} == {
        "id": str(archivo.archivo_id),
        "obra_id": str(archivo.obra_id),
        "referencia_tipo": "IMPORTACION",
        "referencia_id": str(archivo.referencia_id),
        "estado": "DISPONIBLE",
        "nombre_original": NOMBRE_DEL_LIBRO,
        "tipo_mime": TIPO_XLSX,
        "tamano_bytes": len(contenido),
        "hash_sha256": archivo.hash_sha256,
        "subido_por": {"id": str(usuario_id), "nombre": NOMBRE_DEL_DIRECTOR},
    }
    assert _instante(cuerpo["creado_en"]) == reloj_de_prueba.ahora
    assert _instante(cuerpo["confirmado_en"]) == reloj_de_prueba.ahora

    fila = fila_de_archivo(motor_aplicacion, archivo.archivo_id)
    assert fila["estado"] == "DISPONIBLE"
    assert fila["tipo_mime"] == TIPO_XLSX
    assert fila["tamano_bytes"] == len(contenido)
    assert fila["hash_sha256"] == archivo.hash_sha256
    assert fila["confirmado_en"] == reloj_de_prueba.ahora
    assert _tipo_del_objeto(cliente_s3, bucket_de_pruebas, archivo.clave) == TIPO_XLSX

    (asiento,) = asientos_del_archivo(motor_aplicacion, archivo.archivo_id)
    assert asiento["accion"] == "CONFIRMAR"
    assert asiento["usuario_id"] == usuario_id
    assert asiento["ocurrido_en"] == reloj_de_prueba.ahora
    assert asiento["entidad_tipo"] == "archivo"
    assert asiento["entidad_id"] == archivo.archivo_id
    assert asiento["obra_id"] == archivo.obra_id
    assert asiento["motivo"] is None
    assert asiento["regla_negocio"] is None
    assert asiento["datos_antes_es_nulo"] is True
    assert set(asiento["datos_despues"]) == CLAVES_DEL_ASIENTO
    assert asiento["datos_despues"] == {
        "hash_sha256": archivo.hash_sha256,
        "tamano_bytes": len(contenido),
        "tipo_mime": TIPO_XLSX,
        "referencia_tipo": "IMPORTACION",
        "referencia_id": str(archivo.referencia_id),
    }


def test_tkt059_ca04_confirmar_sin_referencia(
    aplicacion_archivos: FastAPI,
    motor_aplicacion: Engine,
    sembrar_usuario: SembrarUsuario,
    libro_catalogo: LibroCatalogo,
) -> None:
    """TC-14b · CA-4 esc. 1 · RNF-19 — un archivo de `OBRA` no lleva `referencia_id`: `200` con `null` y un asiento sin esa clave.

    `ck_archivo_referencia_obligatoria` solo admite un `referencia_id` ausente cuando `referencia_tipo` es
    `OBRA`. La respuesta valida contra `Archivo` y trae `"referencia_id": null`; el `datos_despues` del
    asiento `CONFIRMAR` lleva exactamente el hash, el tamaño, el tipo y `referencia_tipo`, sin
    `referencia_id` (un `"None"` o un `null` ahí confundiría a quien lea la bitácora).
    """
    usuario_id = sembrar_director(sembrar_usuario)
    contenido = libro_de_presupuesto(libro_catalogo)

    with cliente_https(aplicacion_archivos) as cliente:
        sesion_id = abrir_sesion_del_director(cliente)
        archivo = dar_de_alta(
            aplicacion_archivos,
            motor_aplicacion,
            usuario_id=usuario_id,
            contenido=contenido,
            referencia_tipo="OBRA",
            con_referencia=False,
        )
        subir_objeto(archivo)
        assert archivo.referencia_id is None

        respuesta = confirmar_por_http(cliente, sesion_id, archivo.archivo_id)

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    validar_contra("Archivo", cuerpo)
    assert cuerpo["referencia_tipo"] == "OBRA"
    assert "referencia_id" in cuerpo
    assert cuerpo["referencia_id"] is None
    assert cuerpo["estado"] == "DISPONIBLE"
    (asiento,) = asientos_del_archivo(motor_aplicacion, archivo.archivo_id)
    assert asiento["accion"] == "CONFIRMAR"
    assert set(asiento["datos_despues"]) == {
        "hash_sha256",
        "tamano_bytes",
        "tipo_mime",
        "referencia_tipo",
    }
    assert asiento["datos_despues"] == {
        "hash_sha256": archivo.hash_sha256,
        "tamano_bytes": len(contenido),
        "tipo_mime": TIPO_XLSX,
        "referencia_tipo": "OBRA",
    }


# --------------------------------------------------------------------------- TC-15


def test_tkt059_ca04_confirmar_dos_veces(
    almacen: AlmacenS3,
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
    libro_catalogo: LibroCatalogo,
) -> None:
    """TC-15 · CA-4 esc. 2 — confirmar un archivo ya `DISPONIBLE` es idempotente: `200` igual, un solo asiento y sin tocar el almacén.

    La segunda confirmación devuelve el mismo cuerpo, con el mismo `confirmado_en`, aunque el reloj haya
    avanzado. La bitácora conserva **un** `CONFIRMAR`. Un contador sobre el almacén real muestra que
    `metadatos` y `reescribir_tipo` se llamaron una sola vez, en la primera.
    """
    usuario_id = sembrar_director(sembrar_usuario)
    contenido = libro_de_presupuesto(libro_catalogo)
    contador = AlmacenContador(almacen)
    aplicacion = crear_aplicacion_de_archivos(
        almacen=contador.como_almacen(), motor=motor_aplicacion, reloj=reloj_de_prueba
    )

    with cliente_https(aplicacion) as cliente:
        sesion_id = abrir_sesion_del_director(cliente)
        archivo = dar_de_alta(
            aplicacion, motor_aplicacion, usuario_id=usuario_id, contenido=contenido
        )
        subir_objeto(archivo)

        primera = confirmar_por_http(cliente, sesion_id, archivo.archivo_id)
        assert primera.status_code == 200, primera.text
        metadatos_tras_la_primera = list(contador.llamadas_metadatos)
        reescrituras_tras_la_primera = list(contador.reescrituras)
        rangos_tras_la_primera = list(contador.rangos_leidos)
        reloj_de_prueba.avanzar(timedelta(minutes=7))

        segunda = confirmar_por_http(cliente, sesion_id, archivo.archivo_id)

    assert segunda.status_code == 200, segunda.text
    assert segunda.json() == primera.json()
    assert segunda.json()["estado"] == "DISPONIBLE"
    assert metadatos_tras_la_primera == [archivo.clave]
    assert reescrituras_tras_la_primera == [(archivo.clave, TIPO_XLSX)]
    assert rangos_tras_la_primera, "La primera confirmación debe leer el tipo de los bytes"
    assert contador.llamadas_metadatos == metadatos_tras_la_primera, (
        "La segunda confirmación no vuelve a comparar el objeto"
    )
    assert contador.reescrituras == reescrituras_tras_la_primera
    assert contador.rangos_leidos == rangos_tras_la_primera
    assert contador.llamadas_leer_todo == []
    asientos = asientos_del_archivo(motor_aplicacion, archivo.archivo_id, "CONFIRMAR")
    assert len(asientos) == 1
    assert (
        fila_de_archivo(motor_aplicacion, archivo.archivo_id)["confirmado_en"]
        == (asientos[0]["ocurrido_en"])
    )


# --------------------------------------------------------------------------- TC-16


def test_tkt059_ca04_la_bitacora_va_en_la_misma_transaccion(
    aplicacion_archivos: FastAPI,
    motor_aplicacion: Engine,
    sembrar_usuario: SembrarUsuario,
    libro_catalogo: LibroCatalogo,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-16 · CA-4 esc. 1 · RNF-19 — si el asiento falla, la confirmación se deshace: `500` y la fila sigue `PENDIENTE`.

    `cimenta.archivos.aplicacion.confirmacion` importa la auditoría como `from cimenta.auditoria import
    interfaz as auditoria` y llama `auditoria.asentar(...)`; la prueba sustituye esa función por una que
    lanza `RuntimeError("fallo provocado")`. El `UPDATE` de la fila va en la misma transacción que el
    asiento, así que se deshace: `PENDIENTE`, `tipo_mime` y `confirmado_en` nulos y ningún `CONFIRMAR`.
    El `500` es el del contrato (`mensaje` y `correlacion_id`), sin la traza ni el texto del fallo.
    """
    from cimenta.archivos.aplicacion import confirmacion

    usuario_id = sembrar_director(sembrar_usuario)
    contenido = libro_de_presupuesto(libro_catalogo)

    with cliente_https(aplicacion_archivos) as cliente:
        sesion_id = abrir_sesion_del_director(cliente)
        archivo = dar_de_alta(
            aplicacion_archivos, motor_aplicacion, usuario_id=usuario_id, contenido=contenido
        )
        subir_objeto(archivo)

        def asentar_que_falla(*_args: Any, **_kwargs: Any) -> None:
            raise RuntimeError("fallo provocado")

        monkeypatch.setattr(confirmacion.auditoria, "asentar", asentar_que_falla)
        respuesta = confirmar_por_http(cliente, sesion_id, archivo.archivo_id)

    assert respuesta.status_code == 500, respuesta.text
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"mensaje", "correlacion_id"}
    assert cuerpo["correlacion_id"] == respuesta.headers[CABECERA_CORRELACION]
    for pista in ("fallo provocado", "RuntimeError", "Traceback", "cimenta.", "sqlalchemy"):
        assert pista not in respuesta.text
    fila = fila_de_archivo(motor_aplicacion, archivo.archivo_id)
    assert fila["estado"] == "PENDIENTE"
    assert fila["confirmado_en"] is None
    assert fila["tipo_mime"] is None
    assert asientos_del_archivo(motor_aplicacion, archivo.archivo_id) == []


# --------------------------------------------------------------------------- TC-17


def test_tkt059_ca04_confirmar_lee_una_fraccion_acotada(
    almacen: AlmacenS3,
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    sembrar_usuario: SembrarUsuario,
) -> None:
    """TC-17 · CA-4 · PA-T59.14 · RNF-06 — un libro de 26 000 000 bytes se confirma leyendo a lo más 256 KiB.

    El libro de `E-2` (un `.xlsx` real más `xl/media/relleno.bin` de 26 000 000 bytes) se sube por la URL
    prefirmada y se confirma con un contador sobre el almacén real: `200`, `DISPONIBLE` con el tipo `.xlsx`,
    la suma de los bytes que devolvió `leer_rango` no excede 262 144 y `leer_todo` nunca se llamó. El
    tamaño y la suma salen de los metadatos, no de una descarga.
    """
    usuario_id = sembrar_director(sembrar_usuario)
    contenido = libro_con_relleno_de_26_mb()
    contador = AlmacenContador(almacen)
    aplicacion = crear_aplicacion_de_archivos(
        almacen=contador.como_almacen(), motor=motor_aplicacion, reloj=reloj_de_prueba
    )

    with cliente_https(aplicacion) as cliente:
        sesion_id = abrir_sesion_del_director(cliente)
        archivo = dar_de_alta(
            aplicacion, motor_aplicacion, usuario_id=usuario_id, contenido=contenido
        )
        subir_objeto(archivo)

        respuesta = confirmar_por_http(cliente, sesion_id, archivo.archivo_id)

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["estado"] == "DISPONIBLE"
    assert respuesta.json()["tipo_mime"] == TIPO_XLSX
    assert contador.llamadas_leer_todo == [], "Confirmar nunca descarga el objeto entero"
    assert contador.rangos_leidos, "El tipo se lee de los bytes con lecturas por rango"
    assert 0 < contador.bytes_leidos_por_rango <= TOPE_DE_LECTURA_POR_RANGO, (
        f"leer_rango devolvió {contador.bytes_leidos_por_rango} bytes de un objeto de {len(contenido)}"
    )
    assert contador.llamadas_metadatos == [archivo.clave]
    fila = fila_de_archivo(motor_aplicacion, archivo.archivo_id)
    assert fila["estado"] == "DISPONIBLE"
    assert fila["tamano_bytes"] == len(contenido)
    assert fila["tipo_mime"] == TIPO_XLSX


# --------------------------------------------------------------------------- contrato de salida


def test_tkt059_ca04_el_literal_de_referencia_tipo_coincide_con_el_conjunto_de_alta() -> None:
    """TKT-059 · CA-4 · `ck_archivo_referencia_tipo` — el `Literal` de `Archivo.referencia_tipo` admite exactamente los seis valores de `TIPOS_DE_REFERENCIA`, sin uno de más ni de menos."""
    assert set(get_args(Archivo.model_fields["referencia_tipo"].annotation)) == TIPOS_DE_REFERENCIA


# Los rechazos de la confirmación (TC-19 a TC-30) son de la fila 12b y se escriben en
# `test_tkt059_confirmacion_rechazos.py`.
