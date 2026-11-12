"""Ajustes del almacén y de los archivos, y su composición en la fábrica (TKT-059, fila 8): TC-05, TC-06, TC-07 y TC-07b.

Sin Docker: se llama a `servidor.ajustes.cargar_ajustes` con un mapa como entorno y a
`servidor.fabrica.crear_aplicacion` con un motor que nunca conecta. Los símbolos de producción
que la fila crea (`cimenta.archivos.interfaz`, los campos nuevos de `AjustesServidor`) se importan
dentro del cuerpo de cada prueba, para que el rojo sea la ausencia de la funcionalidad y no un error
de colección.

Contrato del mensaje (`ConfiguracionInvalida`): «Configuración incompleta o inválida: VAR1, VAR2.
Defínelas en el entorno; las claves están en .env.example.», con los nombres ordenados y nunca un
valor (RNF-07). Los valores del mapa de estas pruebas son reconocibles para poder afirmar que
ninguno aparece en el mensaje.

Los procesos hijos parten de un entorno sin ninguna variable `CIMENTA_*` (`ENTORNO_BASE`), para que
el `.env` o el entorno de quien desarrolla no decidan el resultado.
"""

import importlib
import io
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from structlog.testing import capture_logs

BACKEND = Path(__file__).resolve().parents[1]
ENTORNO_BASE = {
    nombre: valor
    for nombre, valor in {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}.items()
    if not nombre.startswith("CIMENTA_")
}

VARIABLE_APLICACION = "CIMENTA_DB_CONTRASENA_APLICACION"
CONTRASENA_APLICACION = "secreto-aplicacion-tkt059-4d2e"
BASE = {
    "CIMENTA_DB_HOST": "bd-tkt059.test",
    "CIMENTA_DB_PUERTO": "5439",
    "CIMENTA_DB_NOMBRE": "nombre-tkt059",
}
ALMACEN = {
    "CIMENTA_ALMACEN_ORIGEN": "http://localhost:9000",
    "CIMENTA_ALMACEN_BUCKET": "bucket-tkt059",
    "CIMENTA_ALMACEN_CLAVE_ACCESO": "acceso-tkt059-7b1c",
    "CIMENTA_ALMACEN_CLAVE_SECRETA": "secreta-tkt059-e55f",
}
SIN_BASE = {VARIABLE_APLICACION: CONTRASENA_APLICACION}
CON_BASE_Y_ALMACEN = {VARIABLE_APLICACION: CONTRASENA_APLICACION, **BASE, **ALMACEN}

OMISIONES = {
    "archivos_vida_url_subida": 900,
    "archivos_vida_url_lectura": 300,
    "archivos_umbral_pendiente": 86400,
    "archivos_limite_imagen_bytes": 15728640,
    "archivos_limite_video_bytes": 52428800,
    "archivos_limite_documento_bytes": 26214400,
}

VIDA_SUBIDA = "CIMENTA_ARCHIVOS_VIDA_URL_SUBIDA"
VIDA_LECTURA = "CIMENTA_ARCHIVOS_VIDA_URL_LECTURA"
UMBRAL = "CIMENTA_ARCHIVOS_UMBRAL_PENDIENTE"
LIMITE_IMAGEN = "CIMENTA_ARCHIVOS_LIMITE_IMAGEN_BYTES"
LIMITE_VIDEO = "CIMENTA_ARCHIVOS_LIMITE_VIDEO_BYTES"
LIMITE_DOCUMENTO = "CIMENTA_ARCHIVOS_LIMITE_DOCUMENTO_BYTES"
ENDPOINT = "CIMENTA_ALMACEN_ENDPOINT"


def mensaje_de(*variables: str) -> str:
    """El texto exacto de `ConfiguracionInvalida` para las `variables` dadas, ya ordenadas."""
    return (
        f"Configuración incompleta o inválida: {', '.join(variables)}. "
        "Defínelas en el entorno; las claves están en .env.example."
    )


def sin_valores(mensaje: str, entorno: dict[str, str]) -> bool:
    """Verdadero si ningún valor no vacío del mapa aparece en el mensaje (RNF-07)."""
    return not any(valor in mensaje for valor in entorno.values() if valor)


def limpiar_entorno_del_proceso(monkeypatch: pytest.MonkeyPatch) -> None:
    """Quita del proceso toda variable `CIMENTA_*`: `cargar_ajustes(None)` lee `os.environ`."""
    for nombre in [n for n in os.environ if n.startswith("CIMENTA_")]:
        monkeypatch.delenv(nombre)


# --------------------------------------------------------------------------- TC-05


@pytest.mark.parametrize("estado", ["ausente", "vacia"])
@pytest.mark.parametrize("variable", sorted(ALMACEN))
def test_tkt059_ca02_con_base_el_almacen_es_obligatorio(variable: str, estado: str) -> None:
    """TC-05 · CA-2 esc. 1 · RNF-07 — con las tres variables de base, falta una del almacén: no arranca y el error la nombra sola."""
    from servidor.ajustes import ConfiguracionInvalida, cargar_ajustes

    entorno = dict(CON_BASE_Y_ALMACEN)
    if estado == "ausente":
        del entorno[variable]
    else:
        entorno[variable] = ""

    with pytest.raises(ConfiguracionInvalida) as excepcion:
        cargar_ajustes(entorno)

    mensaje = str(excepcion.value)
    assert mensaje == mensaje_de(variable)
    assert sin_valores(mensaje, entorno)
    assert excepcion.value.__cause__ is None


def test_tkt059_ca02_con_base_y_sin_ninguna_variable_del_almacen_las_nombra_ordenadas() -> None:
    """TC-05 · CA-2 esc. 1 — con base y las cuatro ausentes, el mensaje las nombra todas, ordenadas, y no nombra el endpoint opcional."""
    from servidor.ajustes import ConfiguracionInvalida, cargar_ajustes

    entorno = {VARIABLE_APLICACION: CONTRASENA_APLICACION, **BASE}

    with pytest.raises(ConfiguracionInvalida) as excepcion:
        cargar_ajustes(entorno)

    mensaje = str(excepcion.value)
    assert mensaje == mensaje_de(
        "CIMENTA_ALMACEN_BUCKET",
        "CIMENTA_ALMACEN_CLAVE_ACCESO",
        "CIMENTA_ALMACEN_CLAVE_SECRETA",
        "CIMENTA_ALMACEN_ORIGEN",
    )
    assert ENDPOINT not in mensaje
    assert sin_valores(mensaje, entorno)
    assert excepcion.value.__cause__ is None


def test_tkt059_ca02_con_base_y_el_almacen_completo_los_ajustes_lo_guardan() -> None:
    """TC-05 · CA-2 — con base y las cuatro variables, los ajustes las guardan y el endpoint, opcional, queda nulo."""
    from servidor.ajustes import cargar_ajustes

    ajustes = cargar_ajustes(CON_BASE_Y_ALMACEN)

    assert ajustes.almacen_origen == "http://localhost:9000"
    assert ajustes.almacen_bucket == "bucket-tkt059"
    assert ajustes.almacen_clave_acceso == "acceso-tkt059-7b1c"
    assert ajustes.almacen_clave_secreta is not None
    assert ajustes.almacen_clave_secreta.get_secret_value() == "secreta-tkt059-e55f"
    assert ajustes.almacen_endpoint is None


def test_tkt059_ca02_la_clave_secreta_no_aparece_en_repr_ni_en_el_volcado() -> None:
    """TC-05 · CA-2 · RNF-07 — `SecretStr`: ni `repr`, ni `str`, ni `model_dump_json()` llevan la clave secreta del almacén."""
    from servidor.ajustes import cargar_ajustes

    ajustes = cargar_ajustes(CON_BASE_Y_ALMACEN)

    assert (
        ajustes.almacen_clave_secreta is not None
    )  # anti-verde vacío: el campo existe y está lleno
    for texto in (repr(ajustes), str(ajustes), ajustes.model_dump_json()):
        assert ALMACEN["CIMENTA_ALMACEN_CLAVE_SECRETA"] not in texto
        assert CONTRASENA_APLICACION not in texto


@pytest.mark.parametrize("quitar", sorted(BASE))
@pytest.mark.parametrize("vacia", [False, True])
def test_tkt059_ca02_con_la_base_incompleta_el_almacen_no_se_exige(
    quitar: str, vacia: bool
) -> None:
    """TC-05 · CA-2 esc. 2, CA-R1 — si falta alguna de las tres variables de base, no hay base y el almacén no es obligatorio."""
    from servidor.ajustes import cargar_ajustes

    entorno = {VARIABLE_APLICACION: CONTRASENA_APLICACION, **BASE}
    if vacia:
        entorno[quitar] = ""
    else:
        del entorno[quitar]

    ajustes = cargar_ajustes(entorno)

    assert ajustes.db_contrasena_aplicacion.get_secret_value() == CONTRASENA_APLICACION
    assert ajustes.almacen_bucket is None
    assert ajustes.almacen_clave_acceso is None
    assert ajustes.almacen_clave_secreta is None
    assert ajustes.almacen_origen is None


def test_tkt059_ca02_sin_mapa_tambien_se_exige_el_almacen_con_base(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-05 · CA-2 esc. 1 — el retorno de `cargar_ajustes(None)`, que lee `os.environ`, pasa por la misma exigencia que el del mapa."""
    from servidor.ajustes import ConfiguracionInvalida, cargar_ajustes

    limpiar_entorno_del_proceso(monkeypatch)
    for nombre, valor in {VARIABLE_APLICACION: CONTRASENA_APLICACION, **BASE}.items():
        monkeypatch.setenv(nombre, valor)
    monkeypatch.setenv("CIMENTA_ALMACEN_ORIGEN", ALMACEN["CIMENTA_ALMACEN_ORIGEN"])

    with pytest.raises(ConfiguracionInvalida) as excepcion:
        cargar_ajustes(None)

    mensaje = str(excepcion.value)
    assert mensaje == mensaje_de(
        "CIMENTA_ALMACEN_BUCKET", "CIMENTA_ALMACEN_CLAVE_ACCESO", "CIMENTA_ALMACEN_CLAVE_SECRETA"
    )
    assert CONTRASENA_APLICACION not in mensaje
    assert excepcion.value.__cause__ is None

    for nombre, valor in ALMACEN.items():
        monkeypatch.setenv(nombre, valor)
    ajustes = cargar_ajustes(None)
    assert ajustes.almacen_bucket == "bucket-tkt059"


PROGRAMA_CREAR_APLICACION = """
import io

from servidor.fabrica import crear_aplicacion

crear_aplicacion(destino_registro=io.StringIO())
print("ARRANCO")
"""


def ejecutar_en_proceso(entorno: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", PROGRAMA_CREAR_APLICACION],
        cwd=BACKEND,
        env={**ENTORNO_BASE, **entorno},
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        check=False,
    )


def ultima_linea(texto: str) -> str:
    lineas = [linea for linea in texto.splitlines() if linea.strip()]
    return lineas[-1] if lineas else ""


def test_tkt059_ca02_proceso_con_base_y_sin_bucket_no_arranca() -> None:
    """TC-05 · CA-2 esc. 1 · RNF-07 — `crear_aplicacion()` en un proceso con base y sin `CIMENTA_ALMACEN_BUCKET` termina con ese error y ningún valor."""
    entorno = {k: v for k, v in CON_BASE_Y_ALMACEN.items() if k != "CIMENTA_ALMACEN_BUCKET"}

    proceso = ejecutar_en_proceso(entorno)

    detalle = f"código={proceso.returncode}\n{proceso.stdout}\n{proceso.stderr}"
    assert proceso.returncode != 0, detalle
    assert "ARRANCO" not in proceso.stdout, detalle
    error = ultima_linea(proceso.stderr)
    assert "ConfiguracionInvalida" in error, detalle
    assert mensaje_de("CIMENTA_ALMACEN_BUCKET") in error, detalle
    assert sin_valores(proceso.stdout + proceso.stderr, entorno), detalle


def test_tkt059_ca02_proceso_con_base_y_el_almacen_completo_arranca() -> None:
    """TC-05 · CA-2 — control del proceso hijo: con base y las cuatro variables, `crear_aplicacion()` arranca (el cliente S3 no se construye)."""
    proceso = ejecutar_en_proceso(CON_BASE_Y_ALMACEN)

    detalle = f"código={proceso.returncode}\n{proceso.stdout}\n{proceso.stderr}"
    assert proceso.returncode == 0, detalle
    assert "ARRANCO" in proceso.stdout, detalle


# --------------------------------------------------------------------------- TC-06


def test_tkt059_ca02_sin_base_los_ajustes_del_almacen_quedan_nulos() -> None:
    """TC-06 · CA-2 esc. 2, CA-R1 — con solo la contraseña de aplicación, los cuatro campos del almacén son `None` y no se rechaza nada."""
    from servidor.ajustes import cargar_ajustes

    ajustes = cargar_ajustes(SIN_BASE)

    assert ajustes.almacen_origen is None
    assert ajustes.almacen_bucket is None
    assert ajustes.almacen_clave_acceso is None
    assert ajustes.almacen_clave_secreta is None
    assert ajustes.almacen_endpoint is None


def test_tkt059_ca02_sin_base_arranca_sin_almacen(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-06 · CA-2 esc. 2, CA-R1 — sin base la aplicación sirve `/openapi.json`, el `lifespan` registra `trabajos_omitidos` y el contexto de archivos existe sin almacén."""
    from cimenta.archivos.interfaz import ContextoArchivos

    fabrica = importlib.import_module("servidor.fabrica")
    monkeypatch.setattr(
        fabrica,
        "crear_motor_aplicacion",
        lambda *a, **k: pytest.fail("sin base no se crea el motor"),
    )

    aplicacion = fabrica.crear_aplicacion(destino_registro=io.StringIO(), entorno=dict(SIN_BASE))

    with capture_logs() as registros, TestClient(aplicacion) as cliente:
        assert cliente.get("/openapi.json").status_code == 200

    omitidos = [r for r in registros if r.get("event") == "trabajos_omitidos"]
    assert len(omitidos) == 1
    assert isinstance(aplicacion.state.archivos, ContextoArchivos)


# --------------------------------------------------------------------------- TC-07


def test_tkt059_ca02_las_omisiones_de_los_ajustes_de_archivos() -> None:
    """TC-07 · CA-2 — sin las variables `CIMENTA_ARCHIVOS_*`, valen 900, 300, 86400, 15 MiB, 50 MiB y 25 MiB."""
    from servidor.ajustes import cargar_ajustes

    ajustes = cargar_ajustes(SIN_BASE)

    obtenidos = {campo: getattr(ajustes, campo) for campo in OMISIONES}
    assert obtenidos == OMISIONES


@pytest.mark.parametrize(
    ("variable", "valor"),
    [
        (VIDA_SUBIDA, "59"),
        (VIDA_SUBIDA, "3601"),
        (VIDA_SUBIDA, "abc"),
        (VIDA_LECTURA, "59"),
        (VIDA_LECTURA, "3601"),
        (LIMITE_IMAGEN, "0"),
        (LIMITE_VIDEO, "0"),
        (LIMITE_DOCUMENTO, "0"),
        (UMBRAL, "900"),
        (UMBRAL, "899"),
    ],
)
def test_tkt059_ca02_ajustes_de_archivos_fuera_de_rango(variable: str, valor: str) -> None:
    """TC-07 · CA-2 · RNF-07 — un valor fuera de rango (o un umbral que no supera la vida de subida) se rechaza nombrando solo esa variable, sin su valor."""
    from servidor.ajustes import ConfiguracionInvalida, cargar_ajustes

    entorno = {**SIN_BASE, variable: valor}

    with pytest.raises(ConfiguracionInvalida) as excepcion:
        cargar_ajustes(entorno)

    mensaje = str(excepcion.value)
    assert mensaje == mensaje_de(variable)
    assert valor not in mensaje
    assert excepcion.value.__cause__ is None


@pytest.mark.parametrize(
    ("variable", "valor", "campo", "esperado"),
    [
        (VIDA_SUBIDA, "60", "archivos_vida_url_subida", 60),
        (VIDA_SUBIDA, "3600", "archivos_vida_url_subida", 3600),
        (VIDA_LECTURA, "60", "archivos_vida_url_lectura", 60),
        (VIDA_LECTURA, "3600", "archivos_vida_url_lectura", 3600),
        (LIMITE_IMAGEN, "1", "archivos_limite_imagen_bytes", 1),
        (LIMITE_VIDEO, "1", "archivos_limite_video_bytes", 1),
        (LIMITE_DOCUMENTO, "1", "archivos_limite_documento_bytes", 1),
        (UMBRAL, "901", "archivos_umbral_pendiente", 901),
    ],
)
def test_tkt059_ca02_ajustes_de_archivos_en_el_borde_valido(
    variable: str, valor: str, campo: str, esperado: int
) -> None:
    """TC-07 · CA-2 — los bordes válidos (60 y 3600 en las vidas, 1 en un límite, vida de subida + 1 en el umbral) se aceptan."""
    from servidor.ajustes import cargar_ajustes

    ajustes = cargar_ajustes({**SIN_BASE, variable: valor})

    assert getattr(ajustes, campo) == esperado


def test_tkt059_ca02_el_umbral_se_compara_con_la_vida_de_subida_configurada() -> None:
    """TC-07 · CA-2 — con la vida de subida en 1200, un umbral de 1200 se rechaza y uno de 1201 se acepta."""
    from servidor.ajustes import ConfiguracionInvalida, cargar_ajustes

    with pytest.raises(ConfiguracionInvalida) as excepcion:
        cargar_ajustes({**SIN_BASE, VIDA_SUBIDA: "1200", UMBRAL: "1200"})
    assert str(excepcion.value) == mensaje_de(UMBRAL)

    ajustes = cargar_ajustes({**SIN_BASE, VIDA_SUBIDA: "1200", UMBRAL: "1201"})
    assert (ajustes.archivos_vida_url_subida, ajustes.archivos_umbral_pendiente) == (1200, 1201)


def test_tkt059_ca02_un_umbral_invalido_junto_a_una_vida_invalida_nombra_solo_la_vida() -> None:
    """TC-07 · CA-2 — validador tolerante: si la vida de subida ya falló, el umbral no se compara y el error nombra solo la vida."""
    from servidor.ajustes import ConfiguracionInvalida, cargar_ajustes

    entorno = {**SIN_BASE, VIDA_SUBIDA: "3601", UMBRAL: "3000"}

    with pytest.raises(ConfiguracionInvalida) as excepcion:
        cargar_ajustes(entorno)

    mensaje = str(excepcion.value)
    assert mensaje == mensaje_de(VIDA_SUBIDA)
    assert UMBRAL not in mensaje
    assert "3601" not in mensaje
    assert "3000" not in mensaje


def test_tkt059_ca02_varios_ajustes_de_archivos_invalidos_se_nombran_ordenados() -> None:
    """TC-07 · CA-2 — dos variables inválidas independientes aparecen juntas, ordenadas y sin sus valores."""
    from servidor.ajustes import ConfiguracionInvalida, cargar_ajustes

    entorno = {**SIN_BASE, VIDA_LECTURA: "10", LIMITE_VIDEO: "0"}

    with pytest.raises(ConfiguracionInvalida) as excepcion:
        cargar_ajustes(entorno)

    assert str(excepcion.value) == mensaje_de(LIMITE_VIDEO, VIDA_LECTURA)


@pytest.mark.parametrize("endpoint", ["http://minio:9000", "https://almacen.interno:9443"])
def test_tkt059_ca10_un_endpoint_http_o_https_sin_ruta_se_acepta(endpoint: str) -> None:
    """TC-07 · CA-10 — el endpoint interno admite http o https y un host que no es público, a diferencia del origen."""
    from servidor.ajustes import cargar_ajustes

    ajustes = cargar_ajustes({**SIN_BASE, ENDPOINT: endpoint})

    assert ajustes.almacen_endpoint == endpoint


@pytest.mark.parametrize("endpoint", ["ftp://minio", "http://minio:9000/ruta", "minio:9000"])
def test_tkt059_ca10_un_endpoint_que_no_es_http_sin_ruta_se_rechaza(endpoint: str) -> None:
    """TC-07 · CA-10 · RNF-07 — el error nombra `CIMENTA_ALMACEN_ENDPOINT` y no contiene el valor."""
    from servidor.ajustes import ConfiguracionInvalida, cargar_ajustes

    with pytest.raises(ConfiguracionInvalida) as excepcion:
        cargar_ajustes({**SIN_BASE, ENDPOINT: endpoint})

    mensaje = str(excepcion.value)
    assert mensaje == mensaje_de(ENDPOINT)
    assert endpoint not in mensaje
    assert excepcion.value.__cause__ is None


def test_tkt059_ca10_un_endpoint_vacio_cuenta_como_ausente() -> None:
    """TC-07 · CA-10 · CA-16 de TKT-057 — `CIMENTA_ALMACEN_ENDPOINT` vacío no es un valor: el campo queda nulo."""
    from servidor.ajustes import cargar_ajustes

    ajustes = cargar_ajustes({**SIN_BASE, ENDPOINT: ""})

    assert ajustes.almacen_endpoint is None


def test_tkt059_ca10_con_base_y_sin_endpoint_cargar_ajustes_no_lanza() -> None:
    """TC-07 · CA-10 — el endpoint no es obligatorio con base: sin él, el adaptador usa el origen."""
    from servidor.ajustes import cargar_ajustes

    ajustes = cargar_ajustes(CON_BASE_Y_ALMACEN)

    assert ajustes.almacen_endpoint is None
    assert ajustes.almacen_origen == "http://localhost:9000"


def test_tkt059_ca10_con_base_y_con_endpoint_los_ajustes_lo_guardan() -> None:
    """TC-07 · CA-10 — con base, las cuatro obligatorias y el endpoint interno: se guardan tal cual."""
    from servidor.ajustes import cargar_ajustes

    ajustes = cargar_ajustes({**CON_BASE_Y_ALMACEN, ENDPOINT: "http://minio:9000"})

    assert ajustes.almacen_endpoint == "http://minio:9000"
    assert ajustes.almacen_origen == "http://localhost:9000"


BUCKET = "CIMENTA_ALMACEN_BUCKET"


@pytest.mark.parametrize(
    "bucket",
    ["Mal_Nombre", "a", "ab", "-bucket", "bucket-", "bucket_con_guion_bajo", "x" * 64],
)
def test_tkt059_ca02_un_bucket_con_forma_invalida_se_rechaza_nombrando_solo_su_variable(
    bucket: str,
) -> None:
    """TC-07 · CA-2 · RNF-07 — el nombre del bucket sigue la forma de S3 (3 a 63 caracteres, minúsculas, dígitos, puntos y guiones, sin guion en los extremos): el error nombra solo `CIMENTA_ALMACEN_BUCKET`, con o sin base, y nunca el valor."""
    from servidor.ajustes import ConfiguracionInvalida, cargar_ajustes

    for entorno_base in (SIN_BASE, CON_BASE_Y_ALMACEN):
        entorno = {**entorno_base, BUCKET: bucket}

        with pytest.raises(ConfiguracionInvalida) as excepcion:
            cargar_ajustes(entorno)

        # Igualdad exacta con la plantilla: un valor como «a» aparece en cualquier texto, así que
        # la comparación completa es la que demuestra que el mensaje no lo contiene.
        assert str(excepcion.value) == mensaje_de(BUCKET)
        assert excepcion.value.__cause__ is None


@pytest.mark.parametrize("bucket", ["abc", "a.b-c", "bucket-tkt059", "a" * 63])
def test_tkt059_ca02_un_bucket_con_forma_valida_se_acepta_en_sus_bordes(bucket: str) -> None:
    """TC-07 · CA-2 — 3 y 63 caracteres, con puntos y guiones en medio, son nombres de bucket válidos."""
    from servidor.ajustes import cargar_ajustes

    ajustes = cargar_ajustes({**CON_BASE_Y_ALMACEN, BUCKET: bucket})

    assert ajustes.almacen_bucket == bucket


# --------------------------------------------------------------------------- TC-07 · composición


def motor_sin_destino() -> Any:
    """Un motor que nunca conecta: construirlo no abre ninguna conexión."""
    return create_engine("postgresql+psycopg://u:p@localhost:1/x")


def test_tkt059_ca02_la_configuracion_de_archivos_sale_de_los_ajustes() -> None:
    """TC-07 · CA-2 — `aplicacion.state.archivos.configuracion` lleva las vidas, el umbral y los límites de los ajustes, en timedelta y bytes."""
    from cimenta.archivos.interfaz import ConfiguracionArchivos, ContextoArchivos, LimitesArchivo

    fabrica = importlib.import_module("servidor.fabrica")
    entorno = {
        **SIN_BASE,
        VIDA_SUBIDA: "1200",
        VIDA_LECTURA: "600",
        UMBRAL: "90000",
        LIMITE_IMAGEN: "1000",
        LIMITE_VIDEO: "2000",
        LIMITE_DOCUMENTO: "3000",
    }

    aplicacion = fabrica.crear_aplicacion(
        destino_registro=io.StringIO(), motor=motor_sin_destino(), entorno=entorno
    )

    contexto = aplicacion.state.archivos
    assert isinstance(contexto, ContextoArchivos)
    configuracion = contexto.configuracion
    assert isinstance(configuracion, ConfiguracionArchivos)
    assert configuracion.vida_url_subida == timedelta(seconds=1200)
    assert configuracion.vida_url_lectura == timedelta(seconds=600)
    assert configuracion.umbral_pendiente == timedelta(seconds=90000)
    assert configuracion.limites == LimitesArchivo(
        imagen_bytes=1000, video_bytes=2000, documento_bytes=3000
    )


def test_tkt059_ca02_la_configuracion_de_archivos_por_omision() -> None:
    """TC-07 · CA-2 — con las omisiones, la configuración vale 15 min, 5 min, 24 h y los tres límites por omisión."""
    from cimenta.archivos.interfaz import LimitesArchivo

    fabrica = importlib.import_module("servidor.fabrica")

    aplicacion = fabrica.crear_aplicacion(
        destino_registro=io.StringIO(), motor=motor_sin_destino(), entorno=dict(SIN_BASE)
    )

    configuracion = aplicacion.state.archivos.configuracion
    assert configuracion.vida_url_subida == timedelta(minutes=15)
    assert configuracion.vida_url_lectura == timedelta(minutes=5)
    assert configuracion.umbral_pendiente == timedelta(hours=24)
    assert configuracion.limites == LimitesArchivo(
        imagen_bytes=15728640, video_bytes=52428800, documento_bytes=26214400
    )


def test_tkt059_ca02_el_contexto_usa_el_motor_y_el_reloj_de_la_fabrica() -> None:
    """TC-07 · CA-2 — la fábrica de sesiones del contexto se ata al motor recibido y se reutiliza; el reloj es el inyectado."""
    fabrica = importlib.import_module("servidor.fabrica")
    motor = motor_sin_destino()
    instante = datetime(2026, 10, 21, 9, 0, tzinfo=UTC)

    aplicacion = fabrica.crear_aplicacion(
        destino_registro=io.StringIO(),
        motor=motor,
        reloj=lambda: instante,
        entorno=dict(SIN_BASE),
    )

    contexto = aplicacion.state.archivos
    sesiones = contexto.fabrica_sesiones()
    assert sesiones.kw["bind"] is motor
    assert contexto.fabrica_sesiones() is sesiones
    assert contexto.reloj() == instante


def test_tkt059_ca02_sin_reloj_inyectado_el_contexto_usa_la_hora_actual_con_zona() -> None:
    """TC-07 · CA-2 — sin reloj, el contexto devuelve `datetime.now(UTC)`: con zona y a segundos de ahora."""
    fabrica = importlib.import_module("servidor.fabrica")

    aplicacion = fabrica.crear_aplicacion(
        destino_registro=io.StringIO(), motor=motor_sin_destino(), entorno=dict(SIN_BASE)
    )

    ahora = aplicacion.state.archivos.reloj()
    assert ahora.tzinfo is not None
    assert abs(ahora - datetime.now(UTC)) < timedelta(minutes=1)


# --------------------------------------------------------------------------- TC-07b


class EspiaCrearAlmacen:
    """Sustituye a `crear_almacen_s3` en la fábrica: anota los argumentos y devuelve un objeto nuevo."""

    def __init__(self) -> None:
        self.llamadas: list[dict[str, Any]] = []

    def __call__(self, **argumentos: Any) -> object:
        self.llamadas.append(argumentos)
        return object()


def instalar_espia(monkeypatch: pytest.MonkeyPatch) -> EspiaCrearAlmacen:
    """Sustituye `crear_almacen_s3` en el módulo de la fábrica. Se llama dentro del cuerpo de la prueba:
    mientras la fábrica no importe ese nombre, `setattr` falla ahí y no en la preparación."""
    fabrica = importlib.import_module("servidor.fabrica")
    espia = EspiaCrearAlmacen()
    monkeypatch.setattr(fabrica, "crear_almacen_s3", espia)
    return espia


def crear(**opciones: Any) -> Any:
    fabrica = importlib.import_module("servidor.fabrica")
    return fabrica.crear_aplicacion(destino_registro=io.StringIO(), **opciones)


def test_tkt059_ca02_el_proveedor_del_almacen_es_perezoso(monkeypatch: pytest.MonkeyPatch) -> None:
    """TC-07b · CA-2 esc. 2 — sin las cuatro variables, construir la aplicación no crea el cliente y `almacen()` lanza `AlmacenNoConfigurado`."""
    from cimenta.archivos.interfaz import AlmacenNoConfigurado

    espia = instalar_espia(monkeypatch)
    aplicacion = crear(entorno=dict(SIN_BASE))

    assert espia.llamadas == []
    with pytest.raises(AlmacenNoConfigurado) as excepcion:
        aplicacion.state.archivos.almacen()
    assert isinstance(excepcion.value, RuntimeError)
    assert str(excepcion.value) == "el almacén de objetos no está configurado"
    assert espia.llamadas == []


@pytest.mark.parametrize("falta", sorted(ALMACEN))
def test_tkt059_ca02_con_una_variable_del_almacen_ausente_almacen_lanza(
    monkeypatch: pytest.MonkeyPatch, falta: str
) -> None:
    """TC-07b · CA-2 esc. 2 — basta que falte una de las cuatro obligatorias (sin base no se rechaza el arranque) para que `almacen()` lance sin crear el cliente."""
    from cimenta.archivos.interfaz import AlmacenNoConfigurado

    espia = instalar_espia(monkeypatch)
    entorno = {**SIN_BASE, **{k: v for k, v in ALMACEN.items() if k != falta}}
    aplicacion = crear(entorno=entorno)

    with pytest.raises(AlmacenNoConfigurado):
        aplicacion.state.archivos.almacen()
    assert espia.llamadas == []


def test_tkt059_ca02_el_proveedor_crea_el_adaptador_una_sola_vez(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-07b · CA-2 — con las cuatro variables, construir no crea el cliente; la primera llamada lo crea con los ajustes y la segunda devuelve el mismo objeto."""
    espia = instalar_espia(monkeypatch)
    aplicacion = crear(entorno={**SIN_BASE, **ALMACEN})

    assert espia.llamadas == []
    primero = aplicacion.state.archivos.almacen()
    segundo = aplicacion.state.archivos.almacen()

    assert primero is segundo
    assert espia.llamadas == [
        {
            "endpoint": None,
            "origen": "http://localhost:9000",
            "bucket": "bucket-tkt059",
            "clave_acceso": "acceso-tkt059-7b1c",
            "clave_secreta": "secreta-tkt059-e55f",
        }
    ]


def test_tkt059_ca02_el_proveedor_pasa_el_endpoint_interno_al_adaptador(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-07b · CA-2, CA-10 — con `CIMENTA_ALMACEN_ENDPOINT`, el adaptador recibe ese endpoint y el origen público por separado; la clave secreta llega como cadena."""
    espia = instalar_espia(monkeypatch)
    aplicacion = crear(entorno={**SIN_BASE, **ALMACEN, ENDPOINT: "http://minio:9000"})

    aplicacion.state.archivos.almacen()

    (llamada,) = espia.llamadas
    assert llamada["endpoint"] == "http://minio:9000"
    assert llamada["origen"] == "http://localhost:9000"
    assert type(llamada["clave_secreta"]) is str
    assert llamada["clave_secreta"] == "secreta-tkt059-e55f"


def test_tkt059_ca02_un_almacen_inyectado_se_devuelve_tal_cual(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-07b · CA-2 — con `almacen=` inyectado, `almacen()` devuelve ese objeto aunque no haya variables, y no se crea ningún adaptador."""
    espia = instalar_espia(monkeypatch)
    inyectado = object()

    aplicacion = crear(entorno=dict(SIN_BASE), almacen=inyectado)

    assert aplicacion.state.archivos.almacen() is inyectado
    assert aplicacion.state.archivos.almacen() is inyectado
    assert espia.llamadas == []


def test_tkt059_ca02_un_almacen_inyectado_prevalece_sobre_las_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-07b · CA-2 — con el almacén inyectado y las cuatro variables presentes, gana el inyectado y no se crea el adaptador."""
    espia = instalar_espia(monkeypatch)
    inyectado = object()

    aplicacion = crear(entorno={**SIN_BASE, **ALMACEN}, almacen=inyectado)

    assert aplicacion.state.archivos.almacen() is inyectado
    assert espia.llamadas == []


def test_tkt059_ca02_crear_aplicacion_acepta_almacen_como_argumento_por_nombre() -> None:
    """TC-07b · CA-2 — la firma de `crear_aplicacion` gana `almacen` con omisión `None`."""
    import inspect

    fabrica = importlib.import_module("servidor.fabrica")

    firma = inspect.signature(fabrica.crear_aplicacion).parameters

    assert "almacen" in firma
    assert firma["almacen"].default is None
    assert firma["almacen"].kind is inspect.Parameter.KEYWORD_ONLY
