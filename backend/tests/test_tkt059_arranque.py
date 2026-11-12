"""Barrido de arranque y lector del contenido de archivos (TKT-059, fila 15): TC-37 a TC-42.

Al arrancar, el `lifespan` caduca todo archivo `PENDIENTE` cuya subida venció (`CA-10`) sin tocar el
almacén: el barrido es un `UPDATE` sobre la tabla, y un almacén caído no impide servir. Además la fábrica
conecta el ejecutor del análisis con un lector que devuelve los bytes de un archivo `DISPONIBLE` y rechaza
cualquier otro estado sin llamar al almacén (`CA-11`).

Estas pruebas **siembran a propósito antes de entrar al `TestClient`** (excepción del preámbulo del plan de
pruebas, «Altas dentro del `TestClient`»): lo que comprueban es justamente qué hace el arranque con las filas
que ya existen. Las filas se siembran con `creado_en` relativo al `now()` del motor, que es con lo que
compara el barrido.

PostgreSQL y MinIO reales con testcontainers: el esquema sale de `alembic upgrade head` y las escrituras van
con el rol de aplicación. Ningún `sleep`.
"""

from __future__ import annotations

import hashlib
import io
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session
from structlog.testing import capture_logs

from cimenta.archivos.interfaz import (
    ArchivoNoLegible,
    ConfiguracionArchivos,
    LimitesArchivo,
    construir_contexto,
    crear_lector_contenido,
    definicion_barrido_archivo,
)
from cimenta.presupuesto.interfaz import crear_ejecutor_analisis
from herramientas.soporte_tkt017_api import CONTRASENA_DE_PRUEBA
from herramientas.soporte_tkt059 import (
    NOMBRE_DEL_LIBRO,
    TIPO_XLSX,
    AlmacenContador,
    crear_aplicacion_de_archivos,
)
from servidor import fabrica
from trabajos.barrido import DefinicionBarrido

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta.
    from conftest import DatosPresupuesto, RelojDePrueba, SembrarUsuario
    from mypy_boto3_s3 import S3Client

    from cimenta.archivos.aplicacion.puertos import AlmacenObjetos
    from cimenta.archivos.infraestructura.almacen_s3 import AlmacenS3
    from cimenta.archivos.interfaz import ContextoArchivos

# El umbral de la omisión de `CIMENTA_ARCHIVOS_UMBRAL_PENDIENTE` es de 24 h (86 400 s).
HORAS_VENCIDAS = 25
HORAS_VIGENTES = 1


# --------------------------------------------------------------------------- el almacén que no debe tocarse


class AlmacenQueFalla:
    """Un almacén cuyas seis operaciones anotan la llamada y lanzan el error que la prueba elige.

    Con él se demuestra que el barrido de arranque no habla con el almacén: si lo hiciera, el error subiría
    por el `lifespan` y la aplicación no arrancaría, y `llamadas` diría qué operación fue.
    """

    def __init__(self, crear_error: Callable[[str], Exception]) -> None:
        self._crear_error = crear_error
        self.llamadas: list[str] = []

    def _fallar(self, operacion: str) -> Any:
        self.llamadas.append(operacion)
        raise self._crear_error(operacion)

    def url_subida(self, *argumentos: Any, **nombrados: Any) -> Any:
        return self._fallar("url_subida")

    def metadatos(self, *argumentos: Any, **nombrados: Any) -> Any:
        return self._fallar("metadatos")

    def leer_rango(self, *argumentos: Any, **nombrados: Any) -> Any:
        return self._fallar("leer_rango")

    def leer_todo(self, *argumentos: Any, **nombrados: Any) -> Any:
        return self._fallar("leer_todo")

    def reescribir_tipo(self, *argumentos: Any, **nombrados: Any) -> Any:
        return self._fallar("reescribir_tipo")

    def url_lectura(self, *argumentos: Any, **nombrados: Any) -> Any:
        return self._fallar("url_lectura")

    def como_almacen(self) -> AlmacenObjetos:
        return cast("AlmacenObjetos", self)


# --------------------------------------------------------------------------- la siembra


@dataclass(frozen=True)
class ArchivoSembrado:
    """Una fila de `archivo` sembrada por SQL directo, con el contenido que declara."""

    archivo_id: uuid.UUID
    clave: str
    contenido: bytes


@dataclass(frozen=True)
class Sembrador:
    """Siembra filas de `archivo` con el rol de aplicación y `creado_en` relativo al `now()` del motor."""

    motor: Engine
    usuario_id: uuid.UUID

    def archivo(self, estado: str, *, horas: int = 0) -> ArchivoSembrado:
        """Una fila en ese estado creada hace `horas` horas, con todo lo que sus restricciones exigen."""
        archivo_id = uuid.uuid4()
        obra_id = uuid.uuid4()
        contenido = f"contenido del archivo {archivo_id}".encode()
        clave = f"{obra_id}/{archivo_id}"
        with self.motor.begin() as conexion:
            conexion.execute(
                text(
                    "INSERT INTO archivo (id, obra_id, referencia_tipo, referencia_id, estado, "
                    "clave_objeto, nombre_original, tipo_mime, tamano_bytes, hash_sha256, "
                    "subido_por_id, creado_en, confirmado_en, anulado_por_id, motivo_anulacion, "
                    "anulado_en) VALUES (:id, :obra_id, 'IMPORTACION', :referencia_id, :estado, "
                    ":clave, :nombre, :tipo_mime, :tamano, :hash, :usuario_id, "
                    "now() - make_interval(hours => CAST(:horas AS integer)), "
                    "CASE WHEN :disponible THEN now() END, "
                    "CASE WHEN :anulado THEN CAST(:usuario_id AS uuid) END, "
                    "CASE WHEN :anulado THEN 'Se subió el archivo equivocado' END, "
                    "CASE WHEN :anulado THEN now() END)"
                ),
                {
                    "id": archivo_id,
                    "obra_id": obra_id,
                    "referencia_id": uuid.uuid4(),
                    "estado": estado,
                    "clave": clave,
                    "nombre": NOMBRE_DEL_LIBRO,
                    "tipo_mime": TIPO_XLSX if estado == "DISPONIBLE" else None,
                    "tamano": len(contenido),
                    "hash": hashlib.sha256(contenido).hexdigest(),
                    "usuario_id": self.usuario_id,
                    "horas": horas,
                    "disponible": estado == "DISPONIBLE",
                    "anulado": estado == "ANULADO",
                },
            )
        return ArchivoSembrado(archivo_id=archivo_id, clave=clave, contenido=contenido)

    def estado_de(self, archivo_id: uuid.UUID) -> str:
        with self.motor.connect() as conexion:
            return conexion.execute(
                text("SELECT estado FROM archivo WHERE id = :id"), {"id": archivo_id}
            ).scalar_one()

    def total_de_archivos(self) -> int:
        with self.motor.connect() as conexion:
            return conexion.execute(text("SELECT count(*) FROM archivo")).scalar_one()

    def total_de_la_bitacora(self) -> int:
        with self.motor.connect() as conexion:
            return conexion.execute(text("SELECT count(*) FROM bitacora")).scalar_one()

    def estado_de_la_importacion(self, importacion_id: uuid.UUID) -> str:
        with self.motor.connect() as conexion:
            return conexion.execute(
                text("SELECT estado FROM importacion WHERE id = :id"), {"id": importacion_id}
            ).scalar_one()


@pytest.fixture
def sembrador(motor_aplicacion: Engine, sembrar_usuario: SembrarUsuario) -> Sembrador:
    usuario_id = sembrar_usuario(
        "director.arranque@cimenta.test",
        CONTRASENA_DE_PRUEBA,
        roles=("DIRECTOR_PROYECTOS",),
        nombre="Marta Ibarra",
    )
    return Sembrador(motor=motor_aplicacion, usuario_id=usuario_id)


@pytest.fixture
def poner_objeto(cliente_s3: S3Client, bucket_de_pruebas: str) -> Callable[[ArchivoSembrado], None]:
    """Sube al MinIO real el contenido de un archivo sembrado, bajo la clave de su fila."""

    def _poner(archivo: ArchivoSembrado) -> None:
        cliente_s3.put_object(Bucket=bucket_de_pruebas, Key=archivo.clave, Body=archivo.contenido)

    return _poner


# --------------------------------------------------------------------------- TC-37 a TC-39 · el barrido


def test_tkt059_ca10_el_arranque_caduca_los_pendientes_vencidos(
    sembrador: Sembrador,
    datos_presupuesto: DatosPresupuesto,
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    registro_tecnico: io.StringIO,
) -> None:
    """TC-37 · CA-10 esc. 1, CA-R1 · RNF-19 — el arranque caduca solo el `PENDIENTE` vencido.

    La fila de hace 25 h pasa a `CADUCADO`; la de hace una hora (aún vigente), la `DISPONIBLE` vieja y el
    resto no cambian, ninguna fila se crea ni se borra, la bitácora no recibe asientos y el almacén no se
    toca. La fila de una hora es la que distingue la columna de la marca: con `confirmado_en`, nula en todo
    `PENDIENTE`, el barrido las caducaría todas.
    """
    vencido = sembrador.archivo("PENDIENTE", horas=HORAS_VENCIDAS)
    vigente = sembrador.archivo("PENDIENTE", horas=HORAS_VIGENTES)
    disponible_viejo = sembrador.archivo("DISPONIBLE", horas=HORAS_VENCIDAS)
    importacion_id = datos_presupuesto.importacion(
        estado="ANALIZANDO", latido=datetime.now(tz=UTC) - timedelta(minutes=5)
    )
    filas_antes = sembrador.total_de_archivos()
    bitacora_antes = sembrador.total_de_la_bitacora()
    almacen = AlmacenQueFalla(lambda operacion: AssertionError(f"el arranque llamó a {operacion}"))
    aplicacion = crear_aplicacion_de_archivos(
        almacen=almacen.como_almacen(),
        motor=motor_aplicacion,
        reloj=reloj_de_prueba,
        destino_registro=registro_tecnico,
    )

    with TestClient(aplicacion):
        pass

    assert sembrador.estado_de(vencido.archivo_id) == "CADUCADO"
    assert sembrador.estado_de(vigente.archivo_id) == "PENDIENTE"
    assert sembrador.estado_de(disponible_viejo.archivo_id) == "DISPONIBLE"
    assert sembrador.total_de_archivos() == filas_antes
    assert sembrador.total_de_la_bitacora() == bitacora_antes
    assert almacen.llamadas == []
    assert sembrador.estado_de_la_importacion(importacion_id) == "CON_ERRORES"


def test_tkt059_ca10_el_almacen_caido_no_impide_arrancar(
    sembrador: Sembrador,
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    registro_tecnico: io.StringIO,
) -> None:
    """TC-38 · CA-10 esc. 2 — con el almacén caído la aplicación arranca y el barrido cuenta el archivo.

    El registro `barrido` trae una cuenta por definición, en el orden del `lifespan`: ninguna importación
    y un archivo. Que el barrido de archivos no dependa del almacén es lo que permite arrancar cuando el
    almacén no responde.
    """
    vencido = sembrador.archivo("PENDIENTE", horas=HORAS_VENCIDAS)
    almacen = AlmacenQueFalla(lambda operacion: ConnectionError(f"almacén caído en {operacion}"))
    aplicacion = crear_aplicacion_de_archivos(
        almacen=almacen.como_almacen(),
        motor=motor_aplicacion,
        reloj=reloj_de_prueba,
        destino_registro=registro_tecnico,
    )

    with capture_logs() as registros, TestClient(aplicacion):
        pass

    barridos = [registro for registro in registros if registro.get("event") == "barrido"]
    assert len(barridos) == 1
    assert barridos[0]["cuentas"] == {"importacion": 0, "archivo": 1}
    assert sembrador.estado_de(vencido.archivo_id) == "CADUCADO"
    assert almacen.llamadas == []


def test_tkt059_ca10_definicion_del_barrido() -> None:
    """TC-39 · CA-10 — la definición barre `PENDIENTE` a `CADUCADO` por `creado_en` y no hace nada al vencer."""
    umbral = timedelta(hours=24)

    definicion = definicion_barrido_archivo(umbral)

    assert isinstance(definicion, DefinicionBarrido)
    assert definicion.nombre == "archivo"
    assert definicion.tabla == "archivo"
    assert definicion.estado_intermedio == "PENDIENTE"
    assert definicion.estado_vencido == "CADUCADO"
    assert definicion.columna_marca == "creado_en"
    assert definicion.umbral == umbral
    assert definicion.columna_id == "id"
    assert definicion.columna_estado == "estado"
    sesion_doble = MagicMock(spec=Session)
    definicion.al_vencer(sesion_doble, (uuid.uuid4(), uuid.uuid4()))
    assert sesion_doble.mock_calls == []


# --------------------------------------------------------------------------- TC-40 a TC-42 · el lector


@dataclass(frozen=True)
class EscenaDelLector:
    """El contexto real de `archivos` sobre PostgreSQL y el MinIO de la prueba, con el almacén contado.

    `crear_lector()` llama a `crear_lector_contenido` con el contexto de la escena.
    """

    contexto: ContextoArchivos
    almacen: AlmacenContador

    def crear_lector(self) -> Callable[[uuid.UUID], bytes]:
        return crear_lector_contenido(self.contexto)


@pytest.fixture
def escena_del_lector(
    motor_aplicacion: Engine, reloj_de_prueba: RelojDePrueba, almacen: AlmacenS3
) -> EscenaDelLector:
    contador = AlmacenContador(almacen)
    contexto = construir_contexto(
        proveedor_motor=lambda: motor_aplicacion,
        proveedor_almacen=contador.como_almacen,
        configuracion=ConfiguracionArchivos(
            vida_url_subida=timedelta(minutes=15),
            vida_url_lectura=timedelta(minutes=5),
            umbral_pendiente=timedelta(hours=24),
            limites=LimitesArchivo(
                imagen_bytes=15_728_640, video_bytes=52_428_800, documento_bytes=26_214_400
            ),
        ),
        reloj=reloj_de_prueba,
    )
    return EscenaDelLector(contexto=contexto, almacen=contador)


def test_tkt059_ca11_el_lector_devuelve_los_bytes(
    escena_del_lector: EscenaDelLector,
    sembrador: Sembrador,
    poner_objeto: Callable[[ArchivoSembrado], None],
) -> None:
    """TC-40 · CA-11 esc. 1 · RNF-06 — un archivo `DISPONIBLE` con objeto devuelve exactamente sus bytes."""
    archivo = sembrador.archivo("DISPONIBLE")
    poner_objeto(archivo)

    leer = escena_del_lector.crear_lector()

    contenido = leer(archivo.archivo_id)

    assert contenido == archivo.contenido
    assert escena_del_lector.almacen.llamadas_leer_todo == [archivo.clave]


@pytest.mark.parametrize("estado", ["PENDIENTE", "CADUCADO", "ANULADO", "INEXISTENTE"])
def test_tkt059_ca11_el_lector_rechaza_lo_no_disponible(
    estado: str,
    escena_del_lector: EscenaDelLector,
    sembrador: Sembrador,
    poner_objeto: Callable[[ArchivoSembrado], None],
) -> None:
    """TC-41 · CA-11 esc. 2 · RNF-06 — lo que no está `DISPONIBLE` no se lee, aunque el objeto exista.

    Las filas `PENDIENTE`, `CADUCADO` y `ANULADO` tienen su objeto en el almacén: un lector que no
    comprobara el estado devolvería esos bytes. Para el identificador inexistente no hay fila ni objeto. En
    los cuatro casos el almacén no recibe ninguna lectura.
    """
    leer = escena_del_lector.crear_lector()
    if estado == "INEXISTENTE":
        archivo_id = uuid.uuid4()
    else:
        archivo = sembrador.archivo(estado)
        poner_objeto(archivo)
        archivo_id = archivo.archivo_id

    with pytest.raises(ArchivoNoLegible) as excepcion:
        leer(archivo_id)

    assert isinstance(excepcion.value, RuntimeError)
    assert str(excepcion.value) == f"el archivo {archivo_id} no está DISPONIBLE"
    assert escena_del_lector.almacen.llamadas_leer_todo == []


def test_tkt059_ca11_la_fabrica_conecta_el_lector(
    monkeypatch: pytest.MonkeyPatch,
    sembrador: Sembrador,
    poner_objeto: Callable[[ArchivoSembrado], None],
    motor_aplicacion: Engine,
    reloj_de_prueba: RelojDePrueba,
    almacen: AlmacenS3,
    registro_tecnico: io.StringIO,
) -> None:
    """TC-42 · CA-11 esc. 1 y 2 — el lector que recibe el ejecutor del `lifespan` es el de `archivos`.

    Un espía sustituye a `crear_ejecutor_analisis` en la fábrica, guarda el `leer_contenido` que recibe y
    delega en el real. Con ese lector, un `DISPONIBLE` devuelve sus bytes y un `PENDIENTE` lanza
    `ArchivoNoLegible`; el lector por omisión (`leer_contenido_no_configurado`) no hace ni una cosa ni la otra.
    """
    recibidos: list[Callable[[uuid.UUID], bytes]] = []

    def espia(
        fabrica_sesiones: Any, leer_contenido: Callable[[uuid.UUID], bytes], intervalo: Any
    ) -> Any:
        recibidos.append(leer_contenido)
        return crear_ejecutor_analisis(fabrica_sesiones, leer_contenido, intervalo)

    monkeypatch.setattr(fabrica, "crear_ejecutor_analisis", espia)
    aplicacion = crear_aplicacion_de_archivos(
        almacen=AlmacenContador(almacen).como_almacen(),
        motor=motor_aplicacion,
        reloj=reloj_de_prueba,
        destino_registro=registro_tecnico,
    )

    with TestClient(aplicacion):
        assert len(recibidos) == 1
        leer = recibidos[0]
        disponible = sembrador.archivo("DISPONIBLE")
        poner_objeto(disponible)
        pendiente = sembrador.archivo("PENDIENTE")
        poner_objeto(pendiente)

        assert leer(disponible.archivo_id) == disponible.contenido

        with pytest.raises(ArchivoNoLegible) as excepcion:
            leer(pendiente.archivo_id)
        assert str(excepcion.value) == f"el archivo {pendiente.archivo_id} no está DISPONIBLE"
