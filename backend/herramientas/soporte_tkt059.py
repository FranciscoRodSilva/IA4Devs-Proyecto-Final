"""Ayudas de las pruebas HTTP de la confirmación de archivos (TKT-059, fila 12a y siguientes).

Reúne lo que comparten `test_tkt059_confirmacion.py` y `test_tkt059_confirmacion_concurrencia.py`:
la aplicación real montada sobre un almacén que la prueba elige, el alta de un archivo por la
interfaz publicada (`registrar_archivo`), la subida por la URL prefirmada, la confirmación por HTTP,
el contador de llamadas al almacén y la lectura de la fila y de la bitácora con SQL directo, para que
las pruebas no dependan del repositorio que prueban.

Las altas se hacen **siempre dentro** del bloque `with TestClient(...)`: el reloj de prueba empieza el
2026-10-21 y, desde la fila 15, el barrido de arranque caduca todo `PENDIENTE` sembrado antes de entrar
al cliente (preámbulo del plan de pruebas).

Son ayudantes de prueba: ningún código de producción los importa.
"""

from __future__ import annotations

import hashlib
import io
import random
import uuid
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, TextIO, cast

import httpx
import openpyxl
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from cimenta.archivos.interfaz import AlmacenObjetos, AltaArchivo, registrar_archivo
from herramientas.soporte_tkt017_api import (
    CONTRASENA_DE_PRUEBA,
    ENTORNO_DE_LA_APLICACION,
    NOMBRE_DEL_DIRECTOR,
    TOKEN_CSRF,
    cabeceras_de,
    iniciar_sesion,
)

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta.
    from conftest import LibroCatalogo, SembrarUsuario

# El tipo de la respuesta del cliente de pruebas lo fija Starlette, no `httpx`: no se anota más fino.
Respuesta = Any

TIPO_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
NOMBRE_DEL_LIBRO = "Presupuesto torre 5.xlsx"
CORREO_DEL_DIRECTOR = "director.archivos@cimenta.test"
TAMANO_DEL_RELLENO = 26_000_000
SEMILLA_DEL_RELLENO = 20261111
TOPE_DE_LECTURA_POR_RANGO = 262_144
LIMITE_DE_SUBIDA_SEGUNDOS = 120.0
COLUMNAS_DEL_ASIENTO = (
    "accion",
    "usuario_id",
    "ocurrido_en",
    "motivo",
    "regla_negocio",
    "entidad_tipo",
    "entidad_id",
    "obra_id",
    "datos_antes_es_nulo",
    "datos_despues",
)


def ruta_de_confirmacion(archivo_id: uuid.UUID) -> str:
    return f"/api/v1/archivos/{archivo_id}/confirmacion"


# --------------------------------------------------------------------------- el almacén contado


class AlmacenContador:
    """Envuelve al almacén real, anota cada llamada y delega en él sin cambiar lo que devuelve.

    `gancho_metadatos` se ejecuta **antes** de la llamada real a `metadatos`: la prueba de concurrencia
    lo usa para pausar al hilo A dentro del paso 7 de la confirmación, con la fila ya bloqueada.
    """

    def __init__(self, real: AlmacenObjetos) -> None:
        self.real = real
        self.llamadas_metadatos: list[str] = []
        self.rangos_leidos: list[tuple[str, int, int]] = []
        self.bytes_leidos_por_rango = 0
        self.llamadas_leer_todo: list[str] = []
        self.reescrituras: list[tuple[str, str]] = []
        self.gancho_metadatos: Callable[[str], None] | None = None

    def metadatos(self, clave: str) -> Any:
        self.llamadas_metadatos.append(clave)
        if self.gancho_metadatos is not None:
            self.gancho_metadatos(clave)
        return self.real.metadatos(clave)

    def leer_rango(self, clave: str, inicio: int, fin: int) -> bytes:
        self.rangos_leidos.append((clave, inicio, fin))
        datos = self.real.leer_rango(clave, inicio, fin)
        self.bytes_leidos_por_rango += len(datos)
        return datos

    def leer_todo(self, clave: str) -> bytes:
        self.llamadas_leer_todo.append(clave)
        return self.real.leer_todo(clave)

    def reescribir_tipo(self, clave: str, tipo_mime: str) -> None:
        self.reescrituras.append((clave, tipo_mime))
        self.real.reescribir_tipo(clave, tipo_mime)

    def como_almacen(self) -> AlmacenObjetos:
        """El contador, tipado como el puerto: cumple su forma sin heredarlo."""
        return cast("AlmacenObjetos", self)

    def __getattr__(self, nombre: str) -> Any:
        return getattr(self.real, nombre)


# --------------------------------------------------------------------------- la aplicación y el cliente


def crear_aplicacion_de_archivos(
    *,
    almacen: AlmacenObjetos,
    motor: Engine,
    reloj: Callable[[], datetime],
    destino_registro: TextIO | None = None,
) -> FastAPI:
    """La aplicación real con `archivos` montado, sobre el motor y el reloj de la prueba.

    El registro técnico va a `destino_registro`; sin él, a un búfer que nadie lee.
    """
    from servidor.fabrica import crear_aplicacion

    return crear_aplicacion(
        destino_registro=io.StringIO() if destino_registro is None else destino_registro,
        motor=motor,
        reloj=reloj,
        entorno=ENTORNO_DE_LA_APLICACION,
        almacen=almacen,
    )


def cliente_https(aplicacion: FastAPI) -> TestClient:
    """El cliente de las pruebas de API: HTTPS (cookie `Secure`) y un `500` que se ve como `500`."""
    return TestClient(aplicacion, base_url="https://testserver", raise_server_exceptions=False)


def sembrar_director(
    sembrar_usuario: SembrarUsuario, *, correo: str = CORREO_DEL_DIRECTOR
) -> uuid.UUID:
    """Un Director de Proyectos real: quien sube y quien confirma."""
    return sembrar_usuario(
        correo, CONTRASENA_DE_PRUEBA, roles=("DIRECTOR_PROYECTOS",), nombre=NOMBRE_DEL_DIRECTOR
    )


def abrir_sesion_del_director(
    cliente: TestClient, *, correo: str = CORREO_DEL_DIRECTOR
) -> uuid.UUID:
    return iniciar_sesion(cliente, correo, CONTRASENA_DE_PRUEBA)


# --------------------------------------------------------------------------- contenidos


def libro_de_presupuesto(libro_catalogo: LibroCatalogo) -> bytes:
    """Un `.xlsx` real de openpyxl, con una hoja y dos filas: lo que una persona subiría."""
    libro_catalogo.nueva_hoja("Presupuesto")
    libro_catalogo.escribir_fila("Presupuesto", 1, ["Código", "Descripción", "Unidad"])
    libro_catalogo.escribir_fila(
        "Presupuesto", 2, ["620001", "Muro de tablaroca a dos caras", "M2"]
    )
    return libro_catalogo.bytes()


def libro_con_relleno_de_26_mb() -> bytes:
    """Libro de openpyxl con `xl/media/relleno.bin` de 26 000 000 bytes aleatorios, `ZIP_STORED` (E-2).

    Cabe en el límite de documentos (25 MiB = 26 214 400): el alta lo admite. La semilla fija lo hace
    reproducible.
    """
    memoria = io.BytesIO()
    openpyxl.Workbook().save(memoria)
    relleno = random.Random(SEMILLA_DEL_RELLENO).randbytes(TAMANO_DEL_RELLENO)
    with zipfile.ZipFile(memoria, "a") as archivo_zip:
        archivo_zip.writestr("xl/media/relleno.bin", relleno, compress_type=zipfile.ZIP_STORED)
    return memoria.getvalue()


# --------------------------------------------------------------------------- alta, subida y confirmación


@dataclass(frozen=True)
class ArchivoSubido:
    """Lo que la prueba necesita saber de un archivo dado de alta: su declaración y su URL de subida."""

    alta: AltaArchivo
    obra_id: uuid.UUID
    referencia_id: uuid.UUID | None
    usuario_id: uuid.UUID
    contenido: bytes
    nombre_original: str

    @property
    def archivo_id(self) -> uuid.UUID:
        return self.alta.archivo_id

    @property
    def clave(self) -> str:
        return f"{self.obra_id}/{self.archivo_id}"

    @property
    def hash_sha256(self) -> str:
        return hashlib.sha256(self.contenido).hexdigest()


def dar_de_alta(
    aplicacion: FastAPI,
    motor: Engine,
    *,
    usuario_id: uuid.UUID,
    contenido: bytes,
    nombre_original: str = NOMBRE_DEL_LIBRO,
    tipo_declarado: str = TIPO_XLSX,
    obra_id: uuid.UUID | None = None,
    referencia_tipo: str = "IMPORTACION",
    con_referencia: bool = True,
) -> ArchivoSubido:
    """El alta de la interfaz publicada, en su propia transacción confirmada: la fila queda `PENDIENTE`.

    Declara el tamaño y el SHA-256 **del contenido que recibe**; la prueba que quiere una discrepancia
    sube después otro contenido. Con `con_referencia=False` el alta no lleva `referencia_id`, lo que
    `ck_archivo_referencia_obligatoria` solo admite con `referencia_tipo="OBRA"`.
    """
    obra = obra_id if obra_id is not None else uuid.uuid4()
    referencia_id = uuid.uuid4() if con_referencia else None
    with Session(motor) as sesion_bd, sesion_bd.begin():
        alta = registrar_archivo(
            aplicacion.state.archivos,
            sesion_bd,
            obra_id=obra,
            referencia_tipo=referencia_tipo,
            referencia_id=referencia_id,
            nombre_original=nombre_original,
            tamano_bytes=len(contenido),
            hash_sha256=hashlib.sha256(contenido).hexdigest(),
            tipo_declarado=tipo_declarado,
            usuario_id=usuario_id,
        )
    return ArchivoSubido(
        alta=alta,
        obra_id=obra,
        referencia_id=referencia_id,
        usuario_id=usuario_id,
        contenido=contenido,
        nombre_original=nombre_original,
    )


def subir_objeto(archivo: ArchivoSubido) -> None:
    """`PUT` del contenido por la URL prefirmada, con `application/octet-stream` y la suma firmada.

    El navegador no sabe el tipo real; el tipo lo reescribe la confirmación después de leerlo de los
    bytes. El almacén tiene que aceptar el cuerpo: si no, la prueba falla aquí y no en la confirmación.
    """
    cabeceras = {"Content-Type": "application/octet-stream", **archivo.alta.cabeceras}
    with httpx.Client(timeout=LIMITE_DE_SUBIDA_SEGUNDOS) as cliente:
        respuesta = cliente.put(archivo.alta.url, content=archivo.contenido, headers=cabeceras)
    assert respuesta.status_code == 200, respuesta.text


def confirmar_por_http(
    cliente: TestClient, sesion_id: uuid.UUID, archivo_id: uuid.UUID
) -> Respuesta:
    """`POST /api/v1/archivos/{id}/confirmacion` con la cookie de sesión y un par CSRF coincidente."""
    return cliente.post(
        ruta_de_confirmacion(archivo_id),
        headers=cabeceras_de(sesion_id, TOKEN_CSRF, TOKEN_CSRF),
    )


# --------------------------------------------------------------------------- lectura con SQL directo


def fila_de_archivo(motor: Engine, archivo_id: uuid.UUID) -> dict[str, Any]:
    """La fila de `archivo` por nombre de columna, vista desde una conexión nueva (solo lo confirmado)."""
    with motor.connect() as conexion:
        fila = (
            conexion.execute(
                text(
                    "SELECT estado, tipo_mime, tamano_bytes, hash_sha256, confirmado_en, creado_en, "
                    "clave_objeto, subido_por_id, obra_id FROM archivo WHERE id = :id"
                ),
                {"id": archivo_id},
            )
            .mappings()
            .one()
        )
    return dict(fila)


def asientos_del_archivo(
    motor: Engine, archivo_id: uuid.UUID, accion: str | None = None
) -> list[dict[str, Any]]:
    """Los asientos de bitácora sobre el archivo, por nombre de columna, del más antiguo al más nuevo."""
    consulta = (
        "SELECT accion::text AS accion, usuario_id, ocurrido_en, motivo, regla_negocio, entidad_tipo, "
        "entidad_id, obra_id, datos_antes IS NULL AS datos_antes_es_nulo, datos_despues "
        "FROM bitacora WHERE entidad_tipo = 'archivo' AND entidad_id = :id"
    )
    parametros: dict[str, Any] = {"id": archivo_id}
    if accion is not None:
        consulta += " AND accion::text = :accion"
        parametros["accion"] = accion
    consulta += " ORDER BY ocurrido_en, id"
    with motor.connect() as conexion:
        filas = conexion.execute(text(consulta), parametros).mappings().all()
    return [dict(fila) for fila in filas]
