"""TKT-015b · Arranque (fila B5): TC-63 a TC-67."""

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from structlog.testing import capture_logs

if TYPE_CHECKING:
    from conftest import Conectar, DatosPresupuesto
    from sqlalchemy.engine import Engine

# Mismo valor que `conftest.ENTORNO_DE_PRUEBA` (que las pruebas no importan): Argon2 barato y una
# contraseña de aplicación que nunca conecta con nada.
ENTORNO_DE_PRUEBA = {
    "CIMENTA_ARGON2_TIEMPO": "1",
    "CIMENTA_ARGON2_MEMORIA_KIB": "8192",
    "CIMENTA_ARGON2_PARALELISMO": "1",
    "CIMENTA_DB_CONTRASENA_APLICACION": "contrasena-de-prueba-sin-destino",
}

VARIABLES_DE_BASE = {
    "CIMENTA_DB_HOST": "localhost",
    "CIMENTA_DB_PUERTO": "5432",
    "CIMENTA_DB_NOMBRE": "cimenta",
}


def test_hdu001_esc29_el_arranque_barre_antes_de_servir(
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
    motor_aplicacion: Engine,
) -> None:
    """TC-63 · CA-15 · HDU-001 esc. 29 — el lifespan barre la ANALIZANDO vencida antes de servir."""
    from cimenta.presupuesto.dominio.importacion import TrabajoAnalisis
    from cimenta.presupuesto.infraestructura.ejecutor_analisis import EjecutorCerrado
    from servidor.fabrica import crear_aplicacion

    importacion_id = datos_presupuesto.importacion(
        estado="ANALIZANDO",
        latido=datetime.now(tz=UTC) - timedelta(minutes=5),
    )
    aplicacion = crear_aplicacion(
        destino_registro=io.StringIO(),
        motor=motor_aplicacion,
        entorno=ENTORNO_DE_PRUEBA,
    )

    with TestClient(aplicacion):
        with conectar("aplicacion", base_de_prueba) as conn:
            estado = conn.execute(
                "SELECT estado FROM importacion WHERE id = %s", (importacion_id,)
            ).fetchone()
            errores = conn.execute(
                "SELECT tipo FROM importacion_error WHERE importacion_id = %s",
                (importacion_id,),
            ).fetchall()
        assert estado == ("CON_ERRORES",)
        assert errores == [("PROCESO_INTERRUMPIDO",)]
        assert aplicacion.state.ejecutor_analisis is not None

    trabajo = TrabajoAnalisis(
        importacion_id=uuid.uuid4(), archivo_id=uuid.uuid4(), insumos_existentes={}
    )
    with pytest.raises(EjecutorCerrado):
        aplicacion.state.ejecutor_analisis.encolar(trabajo)


def test_tkt015_ajustes_de_trabajos() -> None:
    """TC-64 · CA-15 · PA-15.4 — omisiones, límites y validador tolerante del umbral."""
    from servidor.ajustes import ConfiguracionInvalida, cargar_ajustes

    base = {"CIMENTA_DB_CONTRASENA_APLICACION": "secreto-de-prueba"}
    ajustes = cargar_ajustes(base)
    assert ajustes.trabajos_intervalo_latido == 5
    assert ajustes.trabajos_umbral_vencimiento == 60

    with pytest.raises(ConfiguracionInvalida) as umbral_bajo:
        cargar_ajustes(
            {
                **base,
                "CIMENTA_TRABAJOS_INTERVALO_LATIDO": "5",
                "CIMENTA_TRABAJOS_UMBRAL_VENCIMIENTO": "10",
            }
        )
    assert "CIMENTA_TRABAJOS_UMBRAL_VENCIMIENTO" in str(umbral_bajo.value)
    assert "CIMENTA_TRABAJOS_INTERVALO_LATIDO" not in str(umbral_bajo.value)
    assert "10" not in str(umbral_bajo.value).replace("CIMENTA_TRABAJOS_UMBRAL_VENCIMIENTO", "")

    with pytest.raises(ConfiguracionInvalida) as intervalo_cero:
        cargar_ajustes({**base, "CIMENTA_TRABAJOS_INTERVALO_LATIDO": "0"})
    assert "CIMENTA_TRABAJOS_INTERVALO_LATIDO" in str(intervalo_cero.value)

    with pytest.raises(ConfiguracionInvalida) as ambos:
        cargar_ajustes(
            {
                **base,
                "CIMENTA_TRABAJOS_INTERVALO_LATIDO": "0",
                "CIMENTA_TRABAJOS_UMBRAL_VENCIMIENTO": "10",
            }
        )
    assert "CIMENTA_TRABAJOS_INTERVALO_LATIDO" in str(ambos.value)
    assert "CIMENTA_TRABAJOS_UMBRAL_VENCIMIENTO" not in str(ambos.value)


def test_tkt015_sin_variables_de_base_el_servidor_arranca(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-65 · TKT-006 CA-R4 y D-2 · P16 — sin variables de base no hay motor ni ejecutor."""
    from servidor import fabrica

    llamadas: list[str] = []

    def motor_prohibido(*args: Any, **kwargs: Any) -> Any:
        llamadas.append("motor")
        raise AssertionError("no debe crearse el motor sin variables de base")

    monkeypatch.setattr(fabrica, "crear_motor_aplicacion", motor_prohibido)
    aplicacion = fabrica.crear_aplicacion(
        destino_registro=io.StringIO(),
        entorno=dict(ENTORNO_DE_PRUEBA),
    )

    with capture_logs() as registros, TestClient(aplicacion) as cliente:
        respuesta = cliente.get("/openapi.json")
        assert respuesta.status_code == 200
        assert aplicacion.state.ejecutor_analisis is None

    omitidos = [r for r in registros if r.get("event") == "trabajos_omitidos"]
    assert len(omitidos) == 1
    assert omitidos[0]["motivo"] == "sin variables de base"
    assert llamadas == []


def test_tkt015_con_base_y_barrido_fallido_no_arranca() -> None:
    """TC-66 · P11 · CA-15 — con base configurada, un barrido que falla impide arrancar."""
    from servidor.fabrica import crear_aplicacion

    class FalloDeConexion(RuntimeError):
        pass

    def conectar_roto() -> Any:
        raise FalloDeConexion("sin conexión")

    motor = create_engine("postgresql+psycopg://u:p@localhost:1/x", creator=conectar_roto)
    aplicacion = crear_aplicacion(
        destino_registro=io.StringIO(),
        motor=motor,
        entorno=ENTORNO_DE_PRUEBA,
    )

    with pytest.raises(Exception) as excepcion, TestClient(aplicacion):
        pass
    causa: BaseException | None = excepcion.value
    cadena: list[BaseException] = []
    while causa is not None and causa not in cadena:
        cadena.append(causa)
        causa = causa.__cause__ or causa.__context__
    assert any(isinstance(e, FalloDeConexion) for e in cadena), cadena


@pytest.mark.parametrize(
    "ausente", [None, "CIMENTA_DB_HOST", "CIMENTA_DB_PUERTO", "CIMENTA_DB_NOMBRE"]
)
@pytest.mark.parametrize("vacia", [False, True])
def test_tkt015_variables_de_base_presentes(ausente: str | None, vacia: bool) -> None:
    """TC-67 · P16 — verdadero solo si las tres variables existen y no están vacías."""
    from herramientas.conexion import variables_de_base_presentes

    entorno = dict(VARIABLES_DE_BASE)
    if ausente is None:
        assert variables_de_base_presentes(entorno) is True
        return
    if vacia:
        entorno[ausente] = ""
    else:
        del entorno[ausente]
    assert variables_de_base_presentes(entorno) is False
