"""Alta de un archivo (TKT-059, fila 9): TC-09 a TC-13b, más el repr de `UrlFirmada`.

`registrar_archivo` es la interfaz de alta que TKT-018 inyecta en su ruta: valida la declaración,
inserta la fila `PENDIENTE` en la sesión **de quien llama** y firma la URL de subida. Ni abre ni
confirma una transacción: si quien llama deshace, la fila no queda.

PostgreSQL y MinIO reales con testcontainers (fixtures de `conftest.py`): el esquema sale de
`alembic upgrade head` y las escrituras van con el rol de aplicación. Las filas se leen con SQL
directo, no con el repositorio, para que estas pruebas no dependan de él.

Los símbolos de producción que la fila crea (`registrar_archivo`, `AltaArchivo`,
`contexto_de_archivos`) se importan dentro del cuerpo de cada prueba, para que el rojo sea la
ausencia de la funcionalidad y no un error de colección.

El espía de `url_subida` envuelve al almacén real y anota cada llamada sin cambiar lo que devuelve:
es lo que demuestra que un rechazo ocurre **antes** de firmar (mutante M-05b).

Esta suite no tiene `test_hdu001_esc24_…`: ese escenario es de TKT-018 (aviso del diseño).
"""

import base64
import hashlib
import io
import secrets
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, cast

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session
from testcontainers.community.minio import MinioContainer

from cimenta.archivos.aplicacion.contexto import (
    ConfiguracionArchivos,
    ContextoArchivos,
    construir_contexto,
)
from cimenta.archivos.aplicacion.puertos import AlmacenObjetos, UrlFirmada
from cimenta.archivos.dominio.declaracion import LimitesArchivo
from cimenta.archivos.infraestructura.almacen_s3 import AlmacenS3
from contrato_error.excepciones import ValidacionRechazada

TIPO_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
CABECERA_SUMA = "x-amz-checksum-sha256"
NOMBRE = "Presupuesto torre 5.xlsx"
TAMANO = 8388608  # 8 MiB: menos que el límite de documentos
HASH = hashlib.sha256(b"presupuesto torre 5").hexdigest()

LIMITE_IMAGEN = 15728640  # 15 MiB
LIMITE_VIDEO = 52428800  # 50 MiB
LIMITE_DOCUMENTO = 26214400  # 25 MiB
VIDA_SUBIDA = timedelta(minutes=15)

ENTORNO = {
    "CIMENTA_ARGON2_TIEMPO": "1",
    "CIMENTA_ARGON2_MEMORIA_KIB": "8192",
    "CIMENTA_ARGON2_PARALELISMO": "1",
    "CIMENTA_DB_CONTRASENA_APLICACION": secrets.token_urlsafe(16),
}

# El `mensaje` de un `422` lo fija el contrato de error: «La petición tiene N campo(s) inválido(s).»
MENSAJE_UN_CAMPO = "La petición tiene 1 campo inválido."


@dataclass
class AlmacenEspia:
    """Envuelve al almacén real: anota cada `url_subida` y delega en él."""

    real: AlmacenObjetos
    llamadas_url_subida: list[dict[str, Any]] = field(default_factory=list)

    def url_subida(
        self, clave: str, *, tamano_bytes: int, sha256_hex: str, vida: timedelta
    ) -> UrlFirmada:
        self.llamadas_url_subida.append(
            {"clave": clave, "tamano_bytes": tamano_bytes, "sha256_hex": sha256_hex, "vida": vida}
        )
        return self.real.url_subida(
            clave, tamano_bytes=tamano_bytes, sha256_hex=sha256_hex, vida=vida
        )

    def __getattr__(self, nombre: str) -> Any:
        return getattr(self.real, nombre)


def _suma_base64(sha256_hex: str) -> str:
    return base64.b64encode(bytes.fromhex(sha256_hex)).decode("ascii")


def _origen_del_almacen(contenedor: MinioContainer) -> str:
    """El origen con el que la fixture `almacen` firma: el del contenedor, sin endpoint aparte."""
    return f"http://{contenedor.get_container_host_ip()}:{contenedor.get_exposed_port(9000)}"


def _cuerpo_de_un_error(
    campo: str, codigo: str, mensaje: str, *, raiz: str = "archivo"
) -> dict[str, object]:
    """El cuerpo completo de un `422` con un solo error de campo, con el campo bajo `raiz`."""
    return {
        "tipo": "VALIDACION",
        "mensaje": MENSAJE_UN_CAMPO,
        "errores": [{"campo": f"{raiz}.{campo}", "codigo": codigo, "mensaje": mensaje}],
        "correlacion_id": "c",
    }


def _mensaje_fuera_de_rango(limite: int, mebibytes: int, categoria: str) -> str:
    return f"El archivo excede el límite de {limite} bytes ({mebibytes} MB) para {categoria}."


@pytest.fixture
def usuario_id(sembrar_usuario: Callable[..., uuid.UUID]) -> uuid.UUID:
    """Quien sube: un usuario real, porque `subido_por_id` tiene clave foránea a `usuario`."""
    return sembrar_usuario(
        "director.alta@cimenta.test", "Contrasena-de-prueba-1", roles=("DIRECTOR_PROYECTOS",)
    )


@pytest.fixture
def espia(almacen: AlmacenS3) -> AlmacenEspia:
    return AlmacenEspia(real=almacen)


@pytest.fixture
def contexto(
    motor_aplicacion: Engine, espia: AlmacenEspia, reloj_de_prueba: Callable[[], Any]
) -> ContextoArchivos:
    """El contexto de la fila 8 sobre la base de prueba, el almacén espiado y el reloj de la prueba."""
    return construir_contexto(
        proveedor_motor=lambda: motor_aplicacion,
        # El espía delega por `__getattr__` en el almacén real: cumple el puerto sin heredarlo.
        proveedor_almacen=lambda: cast(AlmacenObjetos, espia),
        configuracion=ConfiguracionArchivos(
            vida_url_subida=VIDA_SUBIDA,
            vida_url_lectura=timedelta(minutes=5),
            umbral_pendiente=timedelta(hours=24),
            limites=LimitesArchivo(
                imagen_bytes=LIMITE_IMAGEN,
                video_bytes=LIMITE_VIDEO,
                documento_bytes=LIMITE_DOCUMENTO,
            ),
        ),
        reloj=reloj_de_prueba,
    )


def _declaracion(usuario_id: uuid.UUID, obra_id: uuid.UUID, **cambios: Any) -> dict[str, Any]:
    """Los argumentos de una declaración válida de un `.xlsx` de presupuesto; `cambios` rompe uno."""
    valores: dict[str, Any] = {
        "obra_id": obra_id,
        "referencia_tipo": "IMPORTACION",
        "referencia_id": uuid.uuid4(),
        "nombre_original": NOMBRE,
        "tamano_bytes": TAMANO,
        "hash_sha256": HASH,
        "tipo_declarado": TIPO_XLSX,
        "usuario_id": usuario_id,
    }
    valores.update(cambios)
    return valores


def _filas_de_la_obra(sesion_bd: Session, obra_id: uuid.UUID) -> int:
    """Filas de `archivo` de la obra que ve **la sesión de la prueba**, con lo que esa sesión haya escrito."""
    return int(
        sesion_bd.execute(
            text("SELECT count(*) FROM archivo WHERE obra_id = :obra_id"), {"obra_id": obra_id}
        ).scalar_one()
    )


def _filas_vistas_desde_otra_conexion(motor: Engine, obra_id: uuid.UUID) -> int:
    """Filas de la obra que ve otra conexión: solo las confirmadas."""
    with motor.connect() as conexion:
        return int(
            conexion.execute(
                text("SELECT count(*) FROM archivo WHERE obra_id = :obra_id"), {"obra_id": obra_id}
            ).scalar_one()
        )


# --------------------------------------------------------------------------- TC-09


def test_tkt059_ca03_alta_registra_el_pendiente(
    contexto: ContextoArchivos,
    espia: AlmacenEspia,
    sesion_bd: Session,
    motor_aplicacion: Engine,
    usuario_id: uuid.UUID,
    contenedor_minio: MinioContainer,
    reloj_de_prueba: Callable[[], Any],
) -> None:
    """TC-09 · CA-3 esc. 1 · RNF-06 — el alta deja una fila PENDIENTE con la declaración y una URL de subida de 15 minutos."""
    from cimenta.archivos.interfaz import AltaArchivo, registrar_archivo

    obra_id = uuid.uuid4()
    referencia_id = uuid.uuid4()

    alta = registrar_archivo(
        contexto,
        sesion_bd,
        **_declaracion(usuario_id, obra_id, referencia_id=referencia_id),
    )

    assert isinstance(alta, AltaArchivo)
    assert isinstance(alta.archivo_id, uuid.UUID)
    assert alta.metodo == "PUT"
    assert alta.url.startswith(_origen_del_almacen(contenedor_minio) + "/")
    assert "X-Amz-Expires=900" in alta.url
    assert alta.cabeceras == {CABECERA_SUMA: _suma_base64(HASH)}
    assert alta.expira_en == reloj_de_prueba() + timedelta(minutes=15)
    assert alta.expira_en.tzinfo is not None

    # Se firmó una sola vez, con la clave, el tamaño, la suma y la vida de la declaración.
    assert espia.llamadas_url_subida == [
        {
            "clave": f"{obra_id}/{alta.archivo_id}",
            "tamano_bytes": TAMANO,
            "sha256_hex": HASH,
            "vida": VIDA_SUBIDA,
        }
    ]

    fila = (
        sesion_bd.execute(
            text(
                "SELECT obra_id, referencia_tipo, referencia_id, estado, clave_objeto, "
                "nombre_original, tipo_mime, tamano_bytes, hash_sha256, subido_por_id, creado_en, "
                "confirmado_en FROM archivo WHERE id = :id"
            ),
            {"id": alta.archivo_id},
        )
        .mappings()
        .one()
    )
    assert dict(fila) == {
        "obra_id": obra_id,
        "referencia_tipo": "IMPORTACION",
        "referencia_id": referencia_id,
        "estado": "PENDIENTE",
        "clave_objeto": f"{obra_id}/{alta.archivo_id}",
        "nombre_original": NOMBRE,
        "tipo_mime": None,
        "tamano_bytes": TAMANO,
        "hash_sha256": HASH,
        "subido_por_id": usuario_id,
        "creado_en": reloj_de_prueba(),
        "confirmado_en": None,
    }
    # La clave del objeto no revela el nombre original ni lo deja en la URL.
    assert "Presupuesto" not in fila["clave_objeto"]
    assert "Presupuesto" not in alta.url

    # El alta no confirmó nada: otra conexión no la ve hasta que quien llama confirma.
    assert _filas_vistas_desde_otra_conexion(motor_aplicacion, obra_id) == 0
    sesion_bd.commit()
    assert _filas_vistas_desde_otra_conexion(motor_aplicacion, obra_id) == 1


def test_tkt059_ca03_alta_sin_referencia_id_para_la_obra(
    contexto: ContextoArchivos,
    sesion_bd: Session,
    usuario_id: uuid.UUID,
) -> None:
    """TC-09 · CA-3 · invariante 26 — un archivo de referencia `OBRA` se da de alta sin `referencia_id`."""
    from cimenta.archivos.interfaz import registrar_archivo

    obra_id = uuid.uuid4()

    alta = registrar_archivo(
        contexto,
        sesion_bd,
        **_declaracion(usuario_id, obra_id, referencia_tipo="OBRA", referencia_id=None),
    )

    fila = (
        sesion_bd.execute(
            text("SELECT referencia_tipo, referencia_id, estado FROM archivo WHERE id = :id"),
            {"id": alta.archivo_id},
        )
        .mappings()
        .one()
    )
    assert dict(fila) == {"referencia_tipo": "OBRA", "referencia_id": None, "estado": "PENDIENTE"}


# La guarda de F001: `ck_archivo_referencia_tipo` y `ck_archivo_referencia_obligatoria` de la
# migración, reflejadas en el alta para que un descuido de quien llama sea un `ValueError` nombrado
# y no un `IntegrityError` de la base (ni, peor, una URL firmada para una fila que no existe).
TIPOS_DE_REFERENCIA = [
    "AVANCE",
    "ENTRADA_ALMACEN",
    "MERMA",
    "FACTURA_PROVEEDOR",
    "IMPORTACION",
    "OBRA",
]
TIPOS_DE_REFERENCIA_CON_ID_OBLIGATORIO = [t for t in TIPOS_DE_REFERENCIA if t != "OBRA"]
# Datos de la declaración que el mensaje del error no tiene por qué repetir.
OTROS_DATOS_DE_LA_DECLARACION = (NOMBRE, HASH, "usuario", "obra_id", "hash_sha256")


@pytest.mark.parametrize("tipo", ["OTRO", "obra", "Avance", "", " OBRA", "OBRA "])
def test_tkt059_ca03_referencia_tipo_fuera_de_los_seis_se_rechaza(
    tipo: str,
    contexto: ContextoArchivos,
    espia: AlmacenEspia,
    sesion_bd: Session,
    usuario_id: uuid.UUID,
) -> None:
    """TC-09 · CA-3 · invariante 26 — un `referencia_tipo` fuera de los seis es un `ValueError` que nombra el campo, sin firmar ni escribir."""
    from cimenta.archivos.interfaz import registrar_archivo

    obra_id = uuid.uuid4()

    with pytest.raises(ValueError) as excepcion:
        registrar_archivo(
            contexto, sesion_bd, **_declaracion(usuario_id, obra_id, referencia_tipo=tipo)
        )

    mensaje = str(excepcion.value)
    assert "referencia_tipo" in mensaje
    assert "referencia_id" not in mensaje
    assert not any(dato in mensaje for dato in OTROS_DATOS_DE_LA_DECLARACION)
    assert espia.llamadas_url_subida == []
    assert _filas_de_la_obra(sesion_bd, obra_id) == 0


@pytest.mark.parametrize("tipo", TIPOS_DE_REFERENCIA_CON_ID_OBLIGATORIO)
def test_tkt059_ca03_referencia_id_obligatorio_salvo_para_la_obra(
    tipo: str,
    contexto: ContextoArchivos,
    espia: AlmacenEspia,
    sesion_bd: Session,
    usuario_id: uuid.UUID,
) -> None:
    """TC-09 · CA-3 · invariante 26 — un tipo distinto de `OBRA` sin `referencia_id` es un `ValueError` que nombra el campo, sin firmar ni escribir."""
    from cimenta.archivos.interfaz import registrar_archivo

    obra_id = uuid.uuid4()

    with pytest.raises(ValueError) as excepcion:
        registrar_archivo(
            contexto,
            sesion_bd,
            **_declaracion(usuario_id, obra_id, referencia_tipo=tipo, referencia_id=None),
        )

    mensaje = str(excepcion.value)
    assert "referencia_id" in mensaje
    assert not any(dato in mensaje for dato in OTROS_DATOS_DE_LA_DECLARACION)
    assert espia.llamadas_url_subida == []
    assert _filas_de_la_obra(sesion_bd, obra_id) == 0


@pytest.mark.parametrize("tipo", TIPOS_DE_REFERENCIA)
def test_tkt059_ca03_los_seis_tipos_de_referencia_con_id_se_admiten(
    tipo: str,
    contexto: ContextoArchivos,
    espia: AlmacenEspia,
    sesion_bd: Session,
    usuario_id: uuid.UUID,
) -> None:
    """TC-09 · CA-3 · invariante 26 — cada uno de los seis tipos válidos con `referencia_id` se admite: se firma una vez y la fila guarda el tipo."""
    from cimenta.archivos.interfaz import registrar_archivo

    obra_id = uuid.uuid4()
    referencia_id = uuid.uuid4()

    alta = registrar_archivo(
        contexto,
        sesion_bd,
        **_declaracion(usuario_id, obra_id, referencia_tipo=tipo, referencia_id=referencia_id),
    )

    assert len(espia.llamadas_url_subida) == 1
    fila = (
        sesion_bd.execute(
            text("SELECT referencia_tipo, referencia_id FROM archivo WHERE id = :id"),
            {"id": alta.archivo_id},
        )
        .mappings()
        .one()
    )
    assert dict(fila) == {"referencia_tipo": tipo, "referencia_id": referencia_id}


# --------------------------------------------------------------------------- TC-10


def test_tkt059_ca03_alta_se_deshace_con_quien_llama(
    contexto: ContextoArchivos,
    sesion_bd: Session,
    motor_aplicacion: Engine,
    usuario_id: uuid.UUID,
) -> None:
    """TC-10 · CA-3 esc. 1 · RNF-19 — el alta no abre ni confirma transacción: si quien llama deshace, la fila no queda."""
    from cimenta.archivos.interfaz import registrar_archivo

    obra_id = uuid.uuid4()

    with pytest.raises(RuntimeError, match="fallo provocado"), sesion_bd.begin():
        registrar_archivo(contexto, sesion_bd, **_declaracion(usuario_id, obra_id))
        # Dentro de la transacción de quien llama la fila existe y nadie más la ve...
        assert _filas_de_la_obra(sesion_bd, obra_id) == 1
        assert _filas_vistas_desde_otra_conexion(motor_aplicacion, obra_id) == 0
        raise RuntimeError("fallo provocado")

    # ...y al deshacer, no queda ninguna.
    assert _filas_vistas_desde_otra_conexion(motor_aplicacion, obra_id) == 0
    assert _filas_de_la_obra(sesion_bd, obra_id) == 0


# --------------------------------------------------------------------------- TC-11


CATEGORIAS = [
    pytest.param("image/jpeg", LIMITE_IMAGEN, 15, "imágenes", id="imagen"),
    pytest.param("video/mp4", LIMITE_VIDEO, 50, "videos", id="video"),
    pytest.param("application/pdf", LIMITE_DOCUMENTO, 25, "documentos", id="documento"),
]


@pytest.mark.parametrize(("tipo", "limite", "mebibytes", "categoria"), CATEGORIAS)
def test_tkt059_ca03_tamano_declarado_excede_limite(
    tipo: str,
    limite: int,
    mebibytes: int,
    categoria: str,
    contexto: ContextoArchivos,
    espia: AlmacenEspia,
    sesion_bd: Session,
    usuario_id: uuid.UUID,
) -> None:
    """TC-11 · CA-3 esc. 2 · RNF-06 — un tamaño mayor que el límite de la categoría se rechaza con el límite exacto, sin firmar ni escribir."""
    from cimenta.archivos.interfaz import registrar_archivo

    obra_id = uuid.uuid4()

    with pytest.raises(ValidacionRechazada) as excepcion:
        registrar_archivo(
            contexto,
            sesion_bd,
            **_declaracion(usuario_id, obra_id, tipo_declarado=tipo, tamano_bytes=limite + 1),
        )

    assert excepcion.value.estado_http == 422
    assert excepcion.value.cuerpo(frozenset(), "c") == _cuerpo_de_un_error(
        "tamano_bytes", "FUERA_DE_RANGO", _mensaje_fuera_de_rango(limite, mebibytes, categoria)
    )
    # M-05b: el rechazo ocurre antes de firmar y antes de insertar.
    assert espia.llamadas_url_subida == []
    assert _filas_de_la_obra(sesion_bd, obra_id) == 0


def test_tkt059_ca03_tamano_declarado_excede_limite_de_documentos_mensaje_exacto(
    contexto: ContextoArchivos,
    sesion_bd: Session,
    usuario_id: uuid.UUID,
) -> None:
    """TC-11 · CA-3 esc. 2 — el mensaje de un documento de 25 MiB + 1 byte es literalmente el del diseño."""
    from cimenta.archivos.interfaz import registrar_archivo

    with pytest.raises(ValidacionRechazada) as excepcion:
        registrar_archivo(
            contexto,
            sesion_bd,
            **_declaracion(usuario_id, uuid.uuid4(), tamano_bytes=26214401),
        )

    errores = excepcion.value.cuerpo(frozenset(), "c")["errores"]
    assert errores == [
        {
            "campo": "archivo.tamano_bytes",
            "codigo": "FUERA_DE_RANGO",
            "mensaje": "El archivo excede el límite de 26214400 bytes (25 MB) para documentos.",
        }
    ]


@pytest.mark.parametrize(
    ("tipo", "limite"),
    [
        pytest.param("image/jpeg", LIMITE_IMAGEN, id="imagen"),
        pytest.param("video/mp4", LIMITE_VIDEO, id="video"),
        pytest.param("application/pdf", LIMITE_DOCUMENTO, id="documento"),
    ],
)
def test_tkt059_ca03_tamano_igual_al_limite_se_admite(
    tipo: str,
    limite: int,
    contexto: ContextoArchivos,
    espia: AlmacenEspia,
    sesion_bd: Session,
    usuario_id: uuid.UUID,
) -> None:
    """TC-11 · CA-3 esc. 2 — borde: el tamaño igual al límite se admite, se firma una vez y se escribe una fila (y prueba que el espía sí registra)."""
    from cimenta.archivos.interfaz import registrar_archivo

    obra_id = uuid.uuid4()

    alta = registrar_archivo(
        contexto,
        sesion_bd,
        **_declaracion(usuario_id, obra_id, tipo_declarado=tipo, tamano_bytes=limite),
    )

    assert [llamada["tamano_bytes"] for llamada in espia.llamadas_url_subida] == [limite]
    assert _filas_de_la_obra(sesion_bd, obra_id) == 1
    assert alta.metodo == "PUT"


# --------------------------------------------------------------------------- TC-12


@pytest.mark.parametrize(
    "tipo", ["application/vnd.ms-excel", "image/svg+xml", "application/x-msdownload"]
)
def test_tkt059_ca03_tipo_declarado_fuera_de_lista(
    tipo: str,
    contexto: ContextoArchivos,
    espia: AlmacenEspia,
    sesion_bd: Session,
    usuario_id: uuid.UUID,
) -> None:
    """TC-12 · CA-3 esc. 3 · RNF-06 — un tipo fuera de la lista blanca se rechaza solo por el tipo, aunque el tamaño exceda todo límite, sin firmar ni escribir."""
    from cimenta.archivos.interfaz import registrar_archivo

    obra_id = uuid.uuid4()
    mayor_que_todo_limite = LIMITE_VIDEO * 10

    with pytest.raises(ValidacionRechazada) as excepcion:
        registrar_archivo(
            contexto,
            sesion_bd,
            **_declaracion(
                usuario_id, obra_id, tipo_declarado=tipo, tamano_bytes=mayor_que_todo_limite
            ),
        )

    assert excepcion.value.cuerpo(frozenset(), "c") == _cuerpo_de_un_error(
        "tipo_declarado",
        "VALOR_NO_PERMITIDO",
        "El tipo de archivo no está permitido. Se admiten JPEG, PNG, HEIC, WebP, MP4, PDF, XML y XLSX.",
    )
    assert espia.llamadas_url_subida == []
    assert _filas_de_la_obra(sesion_bd, obra_id) == 0


# --------------------------------------------------------------------------- TC-13

MENSAJE_FORMATO_HASH = "El SHA-256 son 64 caracteres hexadecimales en minúsculas."


@pytest.mark.parametrize(
    ("cambio", "campo", "codigo", "mensaje"),
    [
        pytest.param(
            {"hash_sha256": HASH.upper()},
            "hash_sha256",
            "FORMATO",
            MENSAJE_FORMATO_HASH,
            id="hash_con_mayusculas",
        ),
        pytest.param(
            {"hash_sha256": HASH[:63]},
            "hash_sha256",
            "FORMATO",
            MENSAJE_FORMATO_HASH,
            id="hash_de_63_caracteres",
        ),
        pytest.param(
            {"tamano_bytes": 0},
            "tamano_bytes",
            "NO_POSITIVO",
            "El tamaño debe ser mayor que cero.",
            id="tamano_cero",
        ),
        pytest.param(
            {"tamano_bytes": -1},
            "tamano_bytes",
            "NO_POSITIVO",
            "El tamaño debe ser mayor que cero.",
            id="tamano_negativo",
        ),
        pytest.param(
            {"nombre_original": "  "},
            "nombre_original",
            "OBLIGATORIO",
            "El campo es obligatorio.",
            id="nombre_en_blanco",
        ),
        pytest.param(
            {"nombre_original": "n" * 256},
            "nombre_original",
            "DEMASIADO_LARGO",
            "El nombre admite hasta 255 caracteres.",
            id="nombre_de_256_caracteres",
        ),
    ],
)
def test_tkt059_ca03_forma_de_la_declaracion(
    cambio: dict[str, Any],
    campo: str,
    codigo: str,
    mensaje: str,
    contexto: ContextoArchivos,
    espia: AlmacenEspia,
    sesion_bd: Session,
    usuario_id: uuid.UUID,
) -> None:
    """TC-13 · CA-3 · RNF-06 — cada defecto de forma de la declaración es un `422` con su campo, código y mensaje, sin firmar ni escribir."""
    from cimenta.archivos.interfaz import registrar_archivo

    obra_id = uuid.uuid4()

    with pytest.raises(ValidacionRechazada) as excepcion:
        registrar_archivo(contexto, sesion_bd, **_declaracion(usuario_id, obra_id, **cambio))

    assert excepcion.value.cuerpo(frozenset(), "c") == _cuerpo_de_un_error(campo, codigo, mensaje)
    assert espia.llamadas_url_subida == []
    assert _filas_de_la_obra(sesion_bd, obra_id) == 0


@pytest.mark.parametrize(
    "nombre",
    [
        pytest.param("a\x00b", id="nul_en_medio"),
        pytest.param("a\ud800b", id="sustituto_solitario"),
    ],
)
def test_tkt059_ca03_nombre_con_caracteres_no_permitidos(
    nombre: str,
    contexto: ContextoArchivos,
    espia: AlmacenEspia,
    sesion_bd: Session,
    usuario_id: uuid.UUID,
) -> None:
    """TC-13 · CA-3 · RNF-06 — un nombre con NUL o con un sustituto Unicode es un `422` con `FORMATO` en `archivo.nombre_original` y su mensaje exacto, sin firmar ni escribir."""
    from cimenta.archivos.interfaz import registrar_archivo

    obra_id = uuid.uuid4()

    with pytest.raises(ValidacionRechazada) as excepcion:
        registrar_archivo(
            contexto, sesion_bd, **_declaracion(usuario_id, obra_id, nombre_original=nombre)
        )

    assert excepcion.value.cuerpo(frozenset(), "c") == _cuerpo_de_un_error(
        "nombre_original", "FORMATO", "El nombre contiene caracteres no permitidos."
    )
    assert espia.llamadas_url_subida == []
    assert _filas_de_la_obra(sesion_bd, obra_id) == 0


@pytest.mark.parametrize(
    "cambio",
    [
        pytest.param({"nombre_original": "n" * 255}, id="nombre_de_255_caracteres"),
        pytest.param({"tamano_bytes": 1}, id="tamano_de_un_byte"),
    ],
)
def test_tkt059_ca03_forma_de_la_declaracion_bordes_validos(
    cambio: dict[str, Any],
    contexto: ContextoArchivos,
    sesion_bd: Session,
    usuario_id: uuid.UUID,
) -> None:
    """TC-13 · CA-3 — bordes: un nombre de 255 caracteres y un tamaño de 1 byte se admiten."""
    from cimenta.archivos.interfaz import registrar_archivo

    obra_id = uuid.uuid4()

    registrar_archivo(contexto, sesion_bd, **_declaracion(usuario_id, obra_id, **cambio))

    assert _filas_de_la_obra(sesion_bd, obra_id) == 1


def test_tkt059_ca03_varios_defectos_a_la_vez_salen_en_el_orden_de_la_tabla(
    contexto: ContextoArchivos,
    espia: AlmacenEspia,
    sesion_bd: Session,
    usuario_id: uuid.UUID,
) -> None:
    """TC-13 · CA-3 — nombre, tamaño, hash y tipo inválidos a la vez: cuatro errores, en ese orden, en un solo `422`."""
    from cimenta.archivos.interfaz import registrar_archivo

    obra_id = uuid.uuid4()

    with pytest.raises(ValidacionRechazada) as excepcion:
        registrar_archivo(
            contexto,
            sesion_bd,
            **_declaracion(
                usuario_id,
                obra_id,
                nombre_original=" ",
                tamano_bytes=0,
                hash_sha256="xyz",
                tipo_declarado="image/svg+xml",
            ),
        )

    cuerpo = excepcion.value.cuerpo(frozenset(), "c")
    assert cuerpo["mensaje"] == "La petición tiene 4 campos inválidos."
    errores = cuerpo["errores"]
    assert isinstance(errores, list)
    assert [(e["campo"], e["codigo"]) for e in errores] == [
        ("archivo.nombre_original", "OBLIGATORIO"),
        ("archivo.tamano_bytes", "NO_POSITIVO"),
        ("archivo.hash_sha256", "FORMATO"),
        ("archivo.tipo_declarado", "VALOR_NO_PERMITIDO"),
    ]
    assert espia.llamadas_url_subida == []
    assert _filas_de_la_obra(sesion_bd, obra_id) == 0


def test_tkt059_ca03_el_campo_raiz_prefija_los_errores(
    contexto: ContextoArchivos,
    sesion_bd: Session,
    usuario_id: uuid.UUID,
) -> None:
    """TC-13 · CA-3 — `campo_raiz` es el nombre de la propiedad en el cuerpo de quien llama (TKT-018 usa `archivo`): los errores cuelgan de él."""
    from cimenta.archivos.interfaz import registrar_archivo

    with pytest.raises(ValidacionRechazada) as excepcion:
        registrar_archivo(
            contexto,
            sesion_bd,
            **_declaracion(usuario_id, uuid.uuid4(), tamano_bytes=0),
            campo_raiz="declaracion",
        )

    assert excepcion.value.cuerpo(frozenset(), "c") == _cuerpo_de_un_error(
        "tamano_bytes", "NO_POSITIVO", "El tamaño debe ser mayor que cero.", raiz="declaracion"
    )


# --------------------------------------------------------------------------- TC-13b


def test_tkt059_ca03_contexto_de_archivos(
    motor_aplicacion: Engine,
    reloj_de_prueba: Callable[[], Any],
    almacen: AlmacenS3,
) -> None:
    """TC-13b · CA-3 — una ruta `def` con `Depends(contexto_de_archivos)` recibe el mismo objeto que `aplicacion.state.archivos`."""
    from cimenta.archivos.interfaz import contexto_de_archivos
    from servidor.fabrica import crear_aplicacion

    aplicacion = crear_aplicacion(
        destino_registro=io.StringIO(),
        motor=motor_aplicacion,
        reloj=reloj_de_prueba,
        entorno=ENTORNO,
        almacen=almacen,
    )
    recibidos: list[object] = []

    def ruta_de_prueba(
        contexto: Annotated[ContextoArchivos, Depends(contexto_de_archivos)],
    ) -> dict[str, bool]:
        recibidos.append(contexto)
        return {"recibido": True}

    aplicacion.add_api_route("/prueba/contexto-de-archivos", ruta_de_prueba, methods=["GET"])

    with TestClient(
        aplicacion, base_url="https://testserver", raise_server_exceptions=False
    ) as cliente:
        respuesta = cliente.get("/prueba/contexto-de-archivos")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"recibido": True}
    assert len(recibidos) == 1
    assert recibidos[0] is aplicacion.state.archivos
    assert isinstance(recibidos[0], ContextoArchivos)


# --------------------------------------------------------------------------- UrlFirmada


def test_tkt059_ca03_url_firmada_oculta_la_url_en_su_repr() -> None:
    """RNF-06 · ADR-016 — la URL prefirmada es una credencial de portador: ni `repr` ni `str` la dejan en un registro o en un mensaje de aserción."""
    url = "https://almacen.prueba.test/obra/archivo?X-Amz-Signature=firma-secreta-9f3c"
    firmada = UrlFirmada(url=url, cabeceras={CABECERA_SUMA: "c3VtYQ=="})

    for texto in (repr(firmada), str(firmada), f"{firmada}"):
        assert "firma-secreta-9f3c" not in texto
        assert "almacen.prueba.test" not in texto
        assert "X-Amz-Signature" not in texto
    # Ocultarla del repr no la quita del objeto: quien llama sigue leyéndola.
    assert firmada.url == url
    assert firmada.cabeceras == {CABECERA_SUMA: "c3VtYQ=="}
    assert firmada == UrlFirmada(url=url, cabeceras={CABECERA_SUMA: "c3VtYQ=="})


def test_tkt059_ca03_alta_archivo_oculta_la_url_en_su_repr() -> None:
    """RNF-06 · ADR-016 — la URL de subida que devuelve el alta es una credencial de portador: ni `repr` ni `str` la dejan en un registro o en un mensaje de aserción."""
    from cimenta.archivos.interfaz import AltaArchivo

    url = "https://almacen.prueba.test/obra/archivo?X-Amz-Signature=firma-secreta-9f3c"
    archivo_id = uuid.UUID("00000000-0000-0000-0000-0000000000a1")
    expira_en = datetime(2026, 11, 12, 12, 0, tzinfo=UTC)
    cabeceras = {CABECERA_SUMA: "c3VtYQ=="}

    def construir() -> AltaArchivo:
        return AltaArchivo(
            archivo_id=archivo_id,
            url=url,
            metodo="PUT",
            cabeceras=dict(cabeceras),
            expira_en=expira_en,
        )

    alta = construir()

    for texto in (repr(alta), str(alta), f"{alta}"):
        assert "firma-secreta-9f3c" not in texto
        assert "almacen.prueba.test" not in texto
        assert "X-Amz-Signature" not in texto
    # Ocultarla del repr no la quita del objeto: quien llama sigue leyéndola.
    assert alta.url == url
    assert alta == construir()
