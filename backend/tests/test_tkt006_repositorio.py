"""Repositorio de identidad (TKT-006, fila 4): TC-58 y TC-59, con Docker.

Las funciones de `cimenta.identidad.infraestructura.repositorio` reciben la `Session` que abrió el
caso de uso y **ninguna confirma** (regla 8 de CLAUDE.md): la `Session` es la de `sesion_bd`, con el
rol de aplicación, y cada comprobación sobre lo que quedó en la base usa una conexión **nueva**
(`lector`), nunca la misma que escribió. El repositorio no decide nada: compara el correo tal como
llega (normalizar es del dominio) y solo informa si una actualización tocó fila.

Los usuarios los siembra la *fixture* `sembrar_usuario` de `conftest.py`; las sesiones de TC-59 se
siembran con SQL directo para que su rojo no dependa de `insertar_sesion`. El símbolo de producción
(`repositorio`) se importa **dentro** de cada caso, así cada uno falla por sí solo con el
`ModuleNotFoundError` del archivo que falta y la recolección no se cae.
"""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import psycopg
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

Conexion = psycopg.Connection[tuple[Any, ...]]
Conectar = Callable[..., Conexion]

T0 = datetime(2026, 10, 21, 9, 0, tzinfo=UTC)
CORREO_DE_ANA = "ana@cimenta.test"
CONTRASENA_DE_ANA = "Clave-Ana-123"
ROLES_DE_ANA = ("RESIDENTE", "COMPRAS")


# --------------------------------------------------------------------------- ayudas


def sembrar_sesion(
    conexion: Conexion,
    usuario_id: uuid.UUID,
    *,
    creada_en: datetime = T0,
    expira_en: datetime = T0 + timedelta(hours=12),
    ultima_actividad: datetime = T0,
) -> uuid.UUID:
    """Una fila de `sesion` viva, confirmada, escrita sin pasar por el repositorio."""
    identificador = uuid.uuid4()
    conexion.execute(
        "INSERT INTO sesion (id, usuario_id, creada_en, expira_en, ultima_actividad) "
        "VALUES (%s, %s, %s, %s, %s)",
        (identificador, usuario_id, creada_en, expira_en, ultima_actividad),
    )
    return identificador


def fila_de_sesion(conexion: Conexion, sesion_id: uuid.UUID) -> dict[str, Any]:
    """La fila de `sesion` por nombre de columna; falla con nombre si no existe."""
    fila = conexion.execute(
        "SELECT usuario_id, creada_en, expira_en, ultima_actividad, revocada_en, origen_ip, "
        "agente_usuario FROM sesion WHERE id = %s",
        (sesion_id,),
    ).fetchone()
    assert fila is not None, f"No hay ninguna sesión con id {sesion_id}."
    nombres = (
        "usuario_id",
        "creada_en",
        "expira_en",
        "ultima_actividad",
        "revocada_en",
        "origen_ip",
        "agente_usuario",
    )
    return dict(zip(nombres, fila, strict=True))


def contar(conexion: Conexion, tabla: str) -> int:
    fila = conexion.execute(f"SELECT count(*) FROM {tabla}").fetchone()  # noqa: S608
    assert fila is not None
    return int(fila[0])


# --------------------------------------------------------------------------- fixtures


@pytest.fixture
def lector(conectar: Conectar, base_de_prueba: str) -> Callable[[], Conexion]:
    """Abre una conexión nueva del rol de aplicación cada vez: nunca la misma que escribió."""
    return lambda: conectar("aplicacion", base_de_prueba)


@pytest.fixture
def ana(sembrar_usuario: Callable[..., uuid.UUID]) -> uuid.UUID:
    """Un usuario real con dos roles, confirmado antes de que la prueba abra su `Session`."""
    return sembrar_usuario(CORREO_DE_ANA, CONTRASENA_DE_ANA, roles=ROLES_DE_ANA)


# --------------------------------------------------------------------------- TC-58


def test_tkt006_ca02_repositorio_inserta_y_lee(
    sesion_bd: Session, ana: uuid.UUID, lector: Callable[[], Conexion]
) -> None:
    """TC-58 · CA-2 · M11 — insertar_sesion y leer_sesion devuelven las columnas escritas."""
    import cimenta.identidad.infraestructura.repositorio as repositorio

    sesion_id = uuid.uuid4()
    expira_en = T0 + timedelta(hours=12)
    repositorio.insertar_sesion(
        sesion_bd,
        sesion_id=sesion_id,
        usuario_id=ana,
        ahora=T0,
        expira_en=expira_en,
        origen_ip="10.0.0.7",
        agente_usuario="Prueba/1.0",
    )
    sesion_bd.commit()

    guardada = fila_de_sesion(lector(), sesion_id)
    assert guardada == {
        "usuario_id": ana,
        "creada_en": T0,
        "expira_en": expira_en,
        "ultima_actividad": T0,
        "revocada_en": None,
        "origen_ip": "10.0.0.7",
        "agente_usuario": "Prueba/1.0",
    }
    leida = repositorio.leer_sesion(sesion_bd, sesion_id)
    assert leida is not None
    assert leida.usuario_id == ana
    assert leida.nombre == "Ana Torres"
    assert leida.email == CORREO_DE_ANA
    assert leida.expira_en == expira_en
    assert leida.ultima_actividad == T0
    assert leida.revocada_en is None
    assert leida.usuario_activo is True


def test_tkt006_ca02_leer_sesion_inexistente_es_none(sesion_bd: Session, ana: uuid.UUID) -> None:
    """TC-58 · CA-2 · M11 — una sesión que no existe se lee como None, no como una fila vacía."""
    import cimenta.identidad.infraestructura.repositorio as repositorio

    assert repositorio.leer_sesion(sesion_bd, uuid.uuid4()) is None


def test_tkt006_ca10_leer_sesion_trae_el_estado_del_usuario(
    sesion_bd: Session,
    sembrar_usuario: Callable[..., uuid.UUID],
    lector: Callable[[], Conexion],
) -> None:
    """TC-58 · CA-10 · M11 — leer_sesion informa si el usuario sigue activo, para que valide el dominio."""
    import cimenta.identidad.infraestructura.repositorio as repositorio

    desactivado = sembrar_usuario("beto@cimenta.test", "Clave-Beto-123", activo=False)
    sesion_id = sembrar_sesion(lector(), desactivado)

    leida = repositorio.leer_sesion(sesion_bd, sesion_id)

    assert leida is not None
    assert leida.usuario_id == desactivado
    assert leida.usuario_activo is False


def test_tkt006_ca09_leer_sesion_trae_la_revocacion(
    sesion_bd: Session, ana: uuid.UUID, lector: Callable[[], Conexion]
) -> None:
    """TC-58 · CA-9 · M11 — leer_sesion devuelve revocada_en: el repositorio informa, no decide."""
    import cimenta.identidad.infraestructura.repositorio as repositorio

    conexion = lector()
    sesion_id = sembrar_sesion(conexion, ana)
    conexion.execute(
        "UPDATE sesion SET revocada_en = %s WHERE id = %s", (T0 + timedelta(hours=1), sesion_id)
    )

    leida = repositorio.leer_sesion(sesion_bd, sesion_id)

    assert leida is not None
    assert leida.revocada_en == T0 + timedelta(hours=1)


def test_tkt006_ca02_roles_de_devuelve_las_claves_sembradas(
    sesion_bd: Session, ana: uuid.UUID, sembrar_usuario: Callable[..., uuid.UUID]
) -> None:
    """TC-58 · CA-2 · M11 — roles_de devuelve las claves del usuario pedido, sin mezclar a los demás."""
    import cimenta.identidad.infraestructura.repositorio as repositorio

    sembrar_usuario("beto@cimenta.test", "Clave-Beto-123", roles=("DIRECCION_GENERAL",))
    sin_roles = sembrar_usuario("carla@cimenta.test", "Clave-Carla-123")

    roles_de_ana = repositorio.roles_de(sesion_bd, ana)

    assert isinstance(roles_de_ana, frozenset)
    assert roles_de_ana == frozenset({"RESIDENTE", "COMPRAS"})
    assert repositorio.roles_de(sesion_bd, sin_roles) == frozenset()
    assert repositorio.roles_de(sesion_bd, uuid.uuid4()) == frozenset()


def test_tkt006_ca11_roles_de_lee_la_base_en_cada_llamada(
    sesion_bd: Session, ana: uuid.UUID
) -> None:
    """TC-61 (nivel de repositorio) · CA-11 · MT-10 — dos llamadas con la misma `Session` ven el rol retirado entre ambas.

    Un `functools.cache` sobre `roles_de` no se distingue a nivel de petición, porque cada petición abre su
    propia `Session` y la clave de la caché la incluye; con la misma `Session` sí: la segunda llamada
    devolvería lo mismo que la primera. Este caso mata esa forma literal del mutante MT-10.
    """
    import cimenta.identidad.infraestructura.repositorio as repositorio

    antes = repositorio.roles_de(sesion_bd, ana)
    sesion_bd.execute(
        text(
            "DELETE FROM usuario_rol WHERE usuario_id = :usuario "
            "AND rol_id = (SELECT id FROM rol WHERE clave = 'COMPRAS')"
        ),
        {"usuario": ana},
    )
    despues = repositorio.roles_de(sesion_bd, ana)

    assert antes == frozenset({"RESIDENTE", "COMPRAS"})
    assert despues == frozenset({"RESIDENTE"})


def test_tkt006_ca02_buscar_credencial_con_el_correo_exacto(
    sesion_bd: Session, ana: uuid.UUID
) -> None:
    """TC-58 · CA-2 · M11 — con el correo exacto devuelve la credencial; con otro, None."""
    import cimenta.identidad.infraestructura.repositorio as repositorio

    credencial = repositorio.buscar_credencial(sesion_bd, CORREO_DE_ANA)

    assert credencial is not None
    assert credencial.id == ana
    assert credencial.nombre == "Ana Torres"
    assert credencial.email == CORREO_DE_ANA
    assert credencial.activo is True
    assert credencial.password_hash.startswith("$argon2id$")
    assert repositorio.buscar_credencial(sesion_bd, "otra@cimenta.test") is None
    # Normalizar el correo es del dominio: el repositorio compara tal como llega.
    assert repositorio.buscar_credencial(sesion_bd, "ANA@cimenta.test") is None


def test_tkt006_ca04_buscar_credencial_devuelve_al_desactivado(
    sesion_bd: Session, sembrar_usuario: Callable[..., uuid.UUID]
) -> None:
    """TC-58 · CA-4 · M11 — un desactivado se devuelve con activo False: rechazarlo es del dominio."""
    import cimenta.identidad.infraestructura.repositorio as repositorio

    desactivado = sembrar_usuario("beto@cimenta.test", "Clave-Beto-123", activo=False)

    credencial = repositorio.buscar_credencial(sesion_bd, "beto@cimenta.test")

    assert credencial is not None
    assert credencial.id == desactivado
    assert credencial.activo is False


def test_tkt006_ca03_insertar_intento_conserva_el_correo_tal_como_se_escribio(
    sesion_bd: Session, ana: uuid.UUID, lector: Callable[[], Conexion]
) -> None:
    """TC-58 · CA-3 · M11 — el intento guarda el correo escrito y admite un usuario inexistente."""
    import cimenta.identidad.infraestructura.repositorio as repositorio

    repositorio.insertar_intento(
        sesion_bd,
        email="Nadie@Cimenta.TEST",
        usuario_id=None,
        exitoso=False,
        ocurrido_en=T0,
        origen_ip="10.0.0.7",
    )
    repositorio.insertar_intento(
        sesion_bd,
        email=CORREO_DE_ANA,
        usuario_id=ana,
        exitoso=True,
        ocurrido_en=T0 + timedelta(minutes=1),
        origen_ip=None,
    )
    sesion_bd.commit()

    filas = (
        lector()
        .execute(
            "SELECT email, usuario_id, exitoso, ocurrido_en, origen_ip FROM intento_acceso "
            "ORDER BY ocurrido_en"
        )
        .fetchall()
    )
    assert filas == [
        ("Nadie@Cimenta.TEST", None, False, T0, "10.0.0.7"),
        (CORREO_DE_ANA, ana, True, T0 + timedelta(minutes=1), None),
    ]


def test_tkt006_ca02_marcar_ultimo_acceso_no_toca_actualizado_en(
    sesion_bd: Session, ana: uuid.UUID, lector: Callable[[], Conexion]
) -> None:
    """TC-58 · CA-2 · M11 — el último acceso no es un cambio de datos del usuario (asumido)."""
    import cimenta.identidad.infraestructura.repositorio as repositorio

    antes = (
        lector()
        .execute("SELECT ultimo_acceso, actualizado_en FROM usuario WHERE id = %s", (ana,))
        .fetchone()
    )
    assert antes is not None
    assert antes[0] is None

    repositorio.marcar_ultimo_acceso(sesion_bd, ana, T0)
    sesion_bd.commit()

    despues = (
        lector()
        .execute("SELECT ultimo_acceso, actualizado_en FROM usuario WHERE id = %s", (ana,))
        .fetchone()
    )
    assert despues == (T0, antes[1])


def test_tkt006_ca02_el_repositorio_no_confirma(
    sesion_bd: Session, ana: uuid.UUID, lector: Callable[[], Conexion]
) -> None:
    """TC-58 · CA-2 · regla 8 — el repositorio escribe en la transacción de quien llama y no confirma."""
    import cimenta.identidad.infraestructura.repositorio as repositorio

    sesion_id = uuid.uuid4()
    repositorio.insertar_sesion(
        sesion_bd,
        sesion_id=sesion_id,
        usuario_id=ana,
        ahora=T0,
        expira_en=T0 + timedelta(hours=12),
        origen_ip=None,
        agente_usuario=None,
    )
    repositorio.insertar_intento(
        sesion_bd, email=CORREO_DE_ANA, usuario_id=ana, exitoso=True, ocurrido_en=T0, origen_ip=None
    )

    # Dentro de la transacción de quien llama sí está escrito: sin esto, 0 y 0 no probarían nada.
    assert repositorio.leer_sesion(sesion_bd, sesion_id) is not None
    sin_confirmar = (contar(lector(), "sesion"), contar(lector(), "intento_acceso"))
    sesion_bd.rollback()
    tras_deshacer = (contar(lector(), "sesion"), contar(lector(), "intento_acceso"))

    assert sin_confirmar == (0, 0)
    assert tras_deshacer == (0, 0)


# --------------------------------------------------------------------------- TC-59


def test_tkt006_ca06_tocar_sesion_vigente_desliza_la_actividad(
    sesion_bd: Session, ana: uuid.UUID, lector: Callable[[], Conexion]
) -> None:
    """TC-59 · CA-6 · ADR-014 — tocar una sesión vigente devuelve True y mueve ultima_actividad."""
    import cimenta.identidad.infraestructura.repositorio as repositorio

    sesion_id = sembrar_sesion(lector(), ana)
    despues = T0 + timedelta(minutes=5)

    tocada = repositorio.tocar_sesion(sesion_bd, sesion_id, despues)
    sesion_bd.commit()

    guardada = fila_de_sesion(lector(), sesion_id)
    assert tocada is True
    assert guardada["ultima_actividad"] == despues
    assert guardada["revocada_en"] is None
    assert guardada["creada_en"] == T0
    assert guardada["expira_en"] == T0 + timedelta(hours=12)


def test_tkt006_ca09_tocar_y_revocar_respetan_la_revocacion(
    sesion_bd: Session, ana: uuid.UUID, lector: Callable[[], Conexion]
) -> None:
    """TC-59 · CA-9 · ADR-014 — tras revocar, tocar no toca nada; revocar dos veces no pisa la hora."""
    import cimenta.identidad.infraestructura.repositorio as repositorio

    sesion_id = sembrar_sesion(lector(), ana)
    primera_actividad = T0 + timedelta(minutes=5)
    hora_de_revocacion = T0 + timedelta(minutes=10)

    assert repositorio.tocar_sesion(sesion_bd, sesion_id, primera_actividad) is True
    assert repositorio.revocar_sesion(sesion_bd, sesion_id, hora_de_revocacion) is True
    sesion_bd.commit()

    tocada_tras_revocar = repositorio.tocar_sesion(sesion_bd, sesion_id, T0 + timedelta(minutes=20))
    revocada_otra_vez = repositorio.revocar_sesion(sesion_bd, sesion_id, T0 + timedelta(minutes=30))
    sesion_bd.commit()

    guardada = fila_de_sesion(lector(), sesion_id)
    assert tocada_tras_revocar is False
    assert guardada["ultima_actividad"] == primera_actividad
    assert revocada_otra_vez is False
    assert guardada["revocada_en"] == hora_de_revocacion


def test_tkt006_ca09_revocar_no_toca_la_actividad_ni_borra_la_fila(
    sesion_bd: Session, ana: uuid.UUID, lector: Callable[[], Conexion]
) -> None:
    """TC-59 · CA-9 esc. 4 · ADR-014 — revocar escribe revocada_en y conserva la fila y su actividad."""
    import cimenta.identidad.infraestructura.repositorio as repositorio

    sesion_id = sembrar_sesion(lector(), ana)

    revocada = repositorio.revocar_sesion(sesion_bd, sesion_id, T0 + timedelta(minutes=10))
    sesion_bd.commit()

    guardada = fila_de_sesion(lector(), sesion_id)
    assert revocada is True
    assert guardada["revocada_en"] == T0 + timedelta(minutes=10)
    assert guardada["ultima_actividad"] == T0
    assert guardada["usuario_id"] == ana
    assert contar(lector(), "sesion") == 1


def test_tkt006_ca09_tocar_y_revocar_una_sesion_inexistente_devuelven_false(
    sesion_bd: Session, ana: uuid.UUID, lector: Callable[[], Conexion]
) -> None:
    """TC-59 · CA-9 · ADR-014 — sin fila no hay actualización: ambas funciones lo dicen con False."""
    import cimenta.identidad.infraestructura.repositorio as repositorio

    inexistente = uuid.uuid4()

    assert repositorio.tocar_sesion(sesion_bd, inexistente, T0) is False
    assert repositorio.revocar_sesion(sesion_bd, inexistente, T0) is False
    sesion_bd.commit()
    assert contar(lector(), "sesion") == 0
