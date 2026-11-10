"""TKT-017b1, fila B1 · TC-B18 · CA-B1 — `nombres_de_usuarios` y `UsuarioResumen` en `identidad`.

`cimenta.identidad.interfaz` publica `nombres_de_usuarios(sesion_bd, ids) -> dict[UUID, str]`, que
devuelve solo los ids que existen con su nombre, y `UsuarioResumen(BaseModel)` con exactamente `id` y
`nombre` (`P-8`: el nombre de `congelada_por`, `capturado_por` y `actualizado_por` se resuelve sin
que `presupuesto` toque las tablas de `identidad`).

Rojo original (riesgo R-2 de TKT-017a3, aceptado por la persona dueña para módulos ausentes): cuando
se escribió el archivo, los dos símbolos no estaban publicados y cada caso fallaba por el nombre ausente
(`ImportError`). Ese rojo ya está documentado en `impl.md`; hoy `cimenta.identidad.interfaz` los publica
y el archivo corre en verde.

La base es PostgreSQL real con el esquema de `alembic upgrade head` y el rol de aplicación; los
usuarios los siembra la *fixture* `sembrar_usuario`, que confirma antes de abrir la `Session`.
"""

import uuid
from collections.abc import Callable

import pytest
from sqlalchemy.orm import Session

from cimenta.identidad.interfaz import UsuarioResumen, nombres_de_usuarios

SembrarUsuarioFn = Callable[..., uuid.UUID]


@pytest.fixture
def ana(sembrar_usuario: SembrarUsuarioFn) -> uuid.UUID:
    """Un usuario real, confirmado antes de que la prueba abra su `Session`."""
    return sembrar_usuario("ana.nombres@cimenta.test", "Clave-Ana-123", nombre="Ana Torres")


@pytest.fixture
def beto(sembrar_usuario: SembrarUsuarioFn) -> uuid.UUID:
    """Un segundo usuario real, con nombre distinto del de `ana`."""
    return sembrar_usuario("beto.nombres@cimenta.test", "Clave-Beto-123", nombre="Beto Salas")


def test_tkt017_nombres_de_usuarios(sesion_bd: Session, ana: uuid.UUID, beto: uuid.UUID) -> None:
    """TC-B18 · CA-B1 · P-8 — dos ids existentes y uno ajeno dan solo los dos, con su nombre."""
    ajeno = uuid.uuid4()

    resultado = nombres_de_usuarios(sesion_bd, [ana, beto, ajeno])

    assert resultado == {ana: "Ana Torres", beto: "Beto Salas"}


def test_tkt017_nombres_de_usuarios_sin_ids_devuelve_vacio(sesion_bd: Session) -> None:
    """TC-B18 · CA-B1 — una colección vacía de ids da un diccionario vacío, sin consultar nada raro."""
    assert nombres_de_usuarios(sesion_bd, []) == {}
    assert nombres_de_usuarios(sesion_bd, iter(())) == {}


def test_tkt017_nombres_de_usuarios_ids_repetidos_no_duplican(
    sesion_bd: Session, ana: uuid.UUID
) -> None:
    """TC-B18 · CA-B1 — un id repetido aparece una sola vez, con su nombre."""
    resultado = nombres_de_usuarios(sesion_bd, [ana, ana, ana])

    assert resultado == {ana: "Ana Torres"}


def test_tkt017_nombres_de_usuarios_solo_ajenos_no_lanza(sesion_bd: Session) -> None:
    """TC-B18 · CA-B1 — ids que no existen no lanzan: el resultado es vacío."""
    assert nombres_de_usuarios(sesion_bd, [uuid.uuid4(), uuid.uuid4()]) == {}


def test_tkt017_nombres_de_usuarios_acepta_un_iterador(
    sesion_bd: Session, ana: uuid.UUID, beto: uuid.UUID
) -> None:
    """TC-B18 · CA-B1 — la firma pide `Iterable[UUID]`: un generador sirve igual que una lista."""
    resultado = nombres_de_usuarios(sesion_bd, (identificador for identificador in (beto, ana)))

    assert resultado == {ana: "Ana Torres", beto: "Beto Salas"}


def test_tkt017_usuario_resumen_publicado_con_id_y_nombre() -> None:
    """TC-B18 · CA-B1 · P-8 — `UsuarioResumen` se importa de la interfaz y tiene exactamente `id` y `nombre`."""
    assert set(UsuarioResumen.model_fields.keys()) == {"id", "nombre"}
    identificador = uuid.uuid4()
    resumen = UsuarioResumen(id=identificador, nombre="Ana Torres")
    assert resumen.id == identificador
    assert resumen.nombre == "Ana Torres"
