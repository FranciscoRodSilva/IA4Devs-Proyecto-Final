"""Privilegios de TKT-011b, fila B4: TC-43 a TC-46, TC-C1 y TC-INV-3 (parte b).

La migración `0007` crea siete tablas que, por los privilegios por omisión de `0001`, nacen con
`SELECT, INSERT, UPDATE, DELETE` para el rol de aplicación y `SELECT` para el de lectura. La fila B4
añade el único `REVOKE` del ticket: `UPDATE, DELETE, TRUNCATE` sobre `linea_base_concepto`, para que
la copia de conceptos solo se anexe (`CA-17`, invariante 14). Este archivo prueba esos privilegios,
que el bloqueo pesimista de `ADR-004` sigue funcionando con el rol de aplicación sobre una línea base
congelada y que el rol de lectura no gana nada (`CA-R3`, invariante 21).

Cada prueba usa el rol que su criterio nombra, nunca el propietario: la aplicación para escribir y
bloquear, la lectura para comprobar que no escribe, y la migración (superusuario en la suite) solo
para leer el catálogo y como control. Los privilegios se leen por `aclexplode(relacl)`, igual que
`TC-18` de `test_tkt011_regresion.py`, que cubre las doce tablas de `0006`; aquí se prueban las
diecinueve.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Any, NamedTuple

import psycopg
import pytest

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta. Solo mypy
    # necesita el tipo de la fábrica, y las anotaciones no se evalúan.
    from conftest import Conectar, DatosPresupuesto

Conexion = psycopg.Connection[tuple[Any, ...]]

# Las diecinueve tablas del módulo `presupuesto`, copia literal del diseño: las doce de `0006` y las
# siete de `0007`. No se derivan de la migración, para que una tabla que falte se vea.
TABLAS_DE_0006: tuple[str, ...] = (
    "empresa",
    "obra",
    "tipo_partida",
    "insumo",
    "nivel",
    "area",
    "partida",
    "concepto",
    "precio_insumo",
    "apu",
    "apu_insumo",
    "apu_cargo",
)
TABLAS_DE_0007: tuple[str, ...] = (
    "linea_base",
    "linea_base_concepto",
    "explosion_presupuesto",
    "presupuesto_control",
    "importacion",
    "importacion_error",
    "rendimiento_observado",
)
TABLAS_DEL_MODULO: tuple[str, ...] = TABLAS_DE_0006 + TABLAS_DE_0007

# Bloqueo pesimista por (línea base, tipo de partida) de las dos tablas que lo usan (`ADR-004`).
BLOQUEO_DEL_CONTROL = "SELECT id FROM presupuesto_control WHERE linea_base_id = %s AND tipo_partida_id = %s FOR UPDATE"
BLOQUEO_DE_LA_EXPLOSION = (
    "SELECT id FROM explosion_presupuesto "
    "WHERE linea_base_id = %s AND tipo_partida_id = %s FOR UPDATE"
)


# --------------------------------------------------------------------------- ayudas


def privilegios(conexion: Conexion, tabla: str, rol: str) -> set[str]:
    """Conjunto de `privilege_type` que `relacl` concede al rol; vacío si no concede ninguno."""
    filas = conexion.execute(
        "SELECT a.privilege_type FROM pg_class c "
        "CROSS JOIN LATERAL aclexplode(c.relacl) a "
        "JOIN pg_roles g ON g.oid = a.grantee "
        "WHERE c.oid = to_regclass(%s) AND g.rolname = %s",
        (tabla, f"cimenta_{rol}"),
    ).fetchall()
    return {str(fila[0]) for fila in filas}


def tablas_existentes(conexion: Conexion) -> set[str]:
    """Las tablas del módulo que existen de verdad: sin esto, una tabla ausente pasaría por vacía."""
    filas = conexion.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename = ANY(%s)",
        (list(TABLAS_DEL_MODULO),),
    ).fetchall()
    return {str(fila[0]) for fila in filas}


def tiene_privilegio(conexion: Conexion, rol: str, tabla: str, privilegio: str) -> bool:
    fila = conexion.execute(
        "SELECT has_table_privilege(%s, %s, %s)", (f"cimenta_{rol}", tabla, privilegio)
    ).fetchone()
    assert fila is not None
    return bool(fila[0])


def error_de(
    conexion: Conexion, sentencia: str, parametros: tuple[Any, ...] | None = None
) -> psycopg.Error | None:
    """El error con que PostgreSQL rechaza la sentencia; `None` si la acepta."""
    try:
        conexion.execute(sentencia, parametros)
    except psycopg.Error as error:
        return error
    return None


def sqlstate_de(conexion: Conexion, sentencia: str) -> str | None:
    """SQLSTATE con que PostgreSQL rechaza la sentencia; `None` si la acepta."""
    error = error_de(conexion, sentencia)
    return None if error is None else error.sqlstate


def contar(conexion: Conexion, tabla: str) -> int:
    fila = conexion.execute(f"SELECT count(*) FROM {tabla}").fetchone()
    assert fila is not None
    return int(fila[0])


class Bloqueables(NamedTuple):
    """Una línea base `CONGELADA` con un renglón de explosión y un control del tipo `MUROS`."""

    linea_base_id: uuid.UUID
    tipo_partida_id: uuid.UUID
    renglon_id: uuid.UUID
    control_id: uuid.UUID


def congelada_con_renglon_y_control(datos: DatosPresupuesto) -> Bloqueables:
    """Una línea base `CONGELADA` de verdad, con un renglón y un control del tipo `MUROS`.

    El renglón y el control se insertan con la línea base en `BORRADOR`, que es el único estado en
    el que el disparador del invariante 14 admite copias, y después se congela con `UPDATE`, igual
    que el congelado real (`E-2`: es el caso en que el bloqueo importa).
    """
    obra = datos.obra(codigo="AP-058-25")
    linea_base = datos.linea_base(estado="BORRADOR", obra_id=obra)
    muros = datos.tipo_partida(clave="MUROS")
    renglon = datos.renglon_explosion(linea_base_id=linea_base, tipo_partida_id=muros)
    control = datos.control(linea_base_id=linea_base, tipo_partida_id=muros)
    datos.congelar(linea_base)
    return Bloqueables(linea_base, muros, renglon, control)


# --------------------------------------------------------------------------- TC-43


def test_tkt011_ca17_la_copia_de_conceptos_solo_se_anexa(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-43 · CA-17 esc. 1 · invariante 14 — la aplicación solo lee y anexa copias de conceptos.

    Por `aclexplode(relacl)`, el rol de aplicación tiene exactamente `SELECT, INSERT` sobre
    `linea_base_concepto`. Sobre una copia de un `BORRADOR` —donde el disparador del invariante 14
    no interviene—, un `UPDATE` y un `DELETE` reales con ese rol responden `42501`, nombran la
    tabla y la fila sigue como estaba. Control: la misma sentencia con el rol de migración sí cambia
    y sí borra la fila, así que el `42501` es del privilegio y no del disparador.
    """
    copia = datos_presupuesto.copia_concepto(
        codigo="620001",
        cantidad=Decimal("100.0000"),
        precio_unitario=Decimal("250.0000"),
        importe=Decimal("25000.0000"),
    )
    actualizar = "UPDATE linea_base_concepto SET cantidad = %s WHERE id = %s"
    borrar = "DELETE FROM linea_base_concepto WHERE id = %s"
    nueva_cantidad = Decimal("999.0000")

    with conectar("migracion", base_de_prueba) as migracion:
        de_aplicacion = privilegios(migracion, "linea_base_concepto", "aplicacion")
        estado = migracion.execute(
            "SELECT lb.estado FROM linea_base lb "
            "JOIN linea_base_concepto c ON c.linea_base_id = lb.id WHERE c.id = %s",
            (copia,),
        ).fetchone()
    assert estado == ("BORRADOR",), "La precondición exige una copia de un BORRADOR"
    assert de_aplicacion == {"SELECT", "INSERT"}

    aplicacion = conectar("aplicacion", base_de_prueba)
    rechazo_de_actualizar = error_de(aplicacion, actualizar, (nueva_cantidad, copia))
    rechazo_de_borrar = error_de(aplicacion, borrar, (copia,))
    assert rechazo_de_actualizar is not None, "UPDATE con el rol de aplicación debió rechazarse"
    assert rechazo_de_borrar is not None, "DELETE con el rol de aplicación debió rechazarse"
    assert rechazo_de_actualizar.sqlstate == "42501"
    assert rechazo_de_borrar.sqlstate == "42501"
    assert "linea_base_concepto" in (rechazo_de_actualizar.diag.message_primary or "")
    assert "linea_base_concepto" in (rechazo_de_borrar.diag.message_primary or "")

    with conectar("migracion", base_de_prueba) as migracion:
        intacta = migracion.execute(
            "SELECT cantidad, precio_unitario, importe FROM linea_base_concepto WHERE id = %s",
            (copia,),
        ).fetchone()
        assert intacta == (Decimal("100.0000"), Decimal("250.0000"), Decimal("25000.0000"))

        # Control: con el privilegio, la misma sentencia sobre la misma fila sí actúa.
        migracion.execute(actualizar, (nueva_cantidad, copia))
        cambiada = migracion.execute(
            "SELECT cantidad FROM linea_base_concepto WHERE id = %s", (copia,)
        ).fetchone()
        assert cambiada == (nueva_cantidad,)
        migracion.execute(borrar, (copia,))
        assert contar(migracion, "linea_base_concepto") == 0


# --------------------------------------------------------------------------- TC-44


def test_tkt011_ca17_el_bloqueo_pesimista_funciona_con_la_aplicacion(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-44 · CA-17 esc. 2 · ADR-004 · HDU-002 esc. 9 — la aplicación bloquea las filas de una línea base congelada.

    Con el rol de aplicación, `SELECT … FOR UPDATE` sobre `presupuesto_control` y sobre
    `explosion_presupuesto` de una línea base `CONGELADA` devuelve sus filas, y `relacl` concede
    `UPDATE` a la aplicación en las dos: bloquear una fila exige ese privilegio.
    """
    datos = congelada_con_renglon_y_control(datos_presupuesto)

    with conectar("migracion", base_de_prueba) as migracion:
        estado = migracion.execute(
            "SELECT estado FROM linea_base WHERE id = %s", (datos.linea_base_id,)
        ).fetchone()
        control_de_aplicacion = privilegios(migracion, "presupuesto_control", "aplicacion")
        explosion_de_aplicacion = privilegios(migracion, "explosion_presupuesto", "aplicacion")
    assert estado == ("CONGELADA",), "La precondición exige una línea base CONGELADA"

    aplicacion = conectar("aplicacion", base_de_prueba)
    clave = (datos.linea_base_id, datos.tipo_partida_id)
    controles = aplicacion.execute(BLOQUEO_DEL_CONTROL, clave).fetchall()
    renglones = aplicacion.execute(BLOQUEO_DE_LA_EXPLOSION, clave).fetchall()

    assert controles == [(datos.control_id,)]
    assert renglones == [(datos.renglon_id,)]
    assert "UPDATE" in control_de_aplicacion
    assert "UPDATE" in explosion_de_aplicacion


# --------------------------------------------------------------------------- TC-C1


def test_tkt011_ca17_el_bloqueo_pesimista_excluye_a_la_segunda_transaccion(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-C1 · CA-17 esc. 2 · ADR-004 — una sola transacción tiene el bloqueo de (línea base, MUROS).

    La conexión A, con el rol de aplicación, toma `FOR UPDATE` sobre la fila de (L, `MUROS`) en
    `presupuesto_control` y en `explosion_presupuesto` sin confirmar. La conexión B, también con el
    rol de aplicación, pide lo mismo con `NOWAIT` sobre cada tabla y recibe `55P03`
    (`lock_not_available`), no `42501`. Cuando A confirma, B obtiene las dos filas. Sin esta prueba
    el bloqueo sería decorativo: dos transacciones pasarían las dos.
    """
    datos = congelada_con_renglon_y_control(datos_presupuesto)
    clave = (datos.linea_base_id, datos.tipo_partida_id)

    a = conectar("aplicacion", base_de_prueba, autocommit=False)
    b = conectar("aplicacion", base_de_prueba)
    assert a.execute(BLOQUEO_DEL_CONTROL, clave).fetchall() == [(datos.control_id,)]
    assert a.execute(BLOQUEO_DE_LA_EXPLOSION, clave).fetchall() == [(datos.renglon_id,)]

    for consulta in (BLOQUEO_DEL_CONTROL, BLOQUEO_DE_LA_EXPLOSION):
        with pytest.raises(psycopg.errors.LockNotAvailable) as espera:
            b.execute(consulta + " NOWAIT", clave)
        assert espera.value.sqlstate == "55P03"

    a.commit()

    obtenidas = [
        b.execute(consulta + " NOWAIT", clave).fetchall()
        for consulta in (BLOQUEO_DEL_CONTROL, BLOQUEO_DE_LA_EXPLOSION)
    ]
    assert obtenidas == [[(datos.control_id,)], [(datos.renglon_id,)]]


# --------------------------------------------------------------------------- TC-45


def test_tkt011_ca17_la_aplicacion_congela_pero_no_vacia(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-45 · CA-17 esc. 3 · PA-T15 — la aplicación tiene `UPDATE` sobre `linea_base` y `TRUNCATE` sobre nada.

    El `UPDATE` sobre `linea_base` es lo que TKT-017 necesita para congelar. En las diecinueve
    tablas, `has_table_privilege(…, 'TRUNCATE')` es falso, con `SELECT` verdadero como precondición
    para que el falso no sea el de una tabla sin ningún privilegio. `TRUNCATE linea_base_concepto`
    con el rol de aplicación responde `42501` y la tabla conserva su fila: `TRUNCATE` no dispara
    ningún disparador de fila, así que solo el privilegio la protege.
    """
    copia = datos_presupuesto.copia_concepto(codigo="620001")

    with conectar("migracion", base_de_prueba) as migracion:
        existentes = tablas_existentes(migracion)
        de_linea_base = privilegios(migracion, "linea_base", "aplicacion")
        tiene_select = {
            t: tiene_privilegio(migracion, "aplicacion", t, "SELECT") for t in TABLAS_DEL_MODULO
        }
        tiene_truncate = {
            t: tiene_privilegio(migracion, "aplicacion", t, "TRUNCATE") for t in TABLAS_DEL_MODULO
        }
    assert len(TABLAS_DEL_MODULO) == 19
    assert existentes == set(TABLAS_DEL_MODULO)
    assert "UPDATE" in de_linea_base
    assert tiene_select == {t: True for t in TABLAS_DEL_MODULO}
    assert tiene_truncate == {t: False for t in TABLAS_DEL_MODULO}

    aplicacion = conectar("aplicacion", base_de_prueba)
    rechazo = error_de(aplicacion, "TRUNCATE linea_base_concepto")
    assert rechazo is not None, "TRUNCATE con el rol de aplicación debió rechazarse"
    assert rechazo.sqlstate == "42501"
    assert "linea_base_concepto" in (rechazo.diag.message_primary or "")

    with conectar("migracion", base_de_prueba) as migracion:
        filas = migracion.execute("SELECT id FROM linea_base_concepto").fetchall()
    assert filas == [(copia,)]


# --------------------------------------------------------------------------- TC-46


def test_tkt011_ca17_el_rol_de_lectura_no_escribe(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> None:
    """TC-46 · CA-17 esc. 4 · CA-R3 — la lectura tiene exactamente `SELECT` en las diecinueve tablas.

    Un `INSERT` real en `linea_base` con el rol de lectura responde `42501`, nombra la tabla y la
    tabla sigue vacía. La obra y el usuario existen, para que el rechazo sea el del privilegio y no
    el de una clave foránea que falta.
    """
    obra = datos_presupuesto.obra(codigo="AP-058-25")
    usuario = datos_presupuesto.usuario()

    with conectar("migracion", base_de_prueba) as migracion:
        existentes = tablas_existentes(migracion)
        de_lectura = {t: privilegios(migracion, t, "lectura") for t in TABLAS_DEL_MODULO}
    assert existentes == set(TABLAS_DEL_MODULO)
    assert de_lectura == {t: {"SELECT"} for t in TABLAS_DEL_MODULO}

    lectura = conectar("lectura", base_de_prueba)
    rechazo = error_de(
        lectura,
        "INSERT INTO linea_base (id, obra_id, version, estado, importe_venta, creado_por_id) "
        "VALUES (%s, %s, 1, 'BORRADOR', %s, %s)",
        (uuid.uuid4(), obra, Decimal("1000000.0000"), usuario),
    )
    assert rechazo is not None, "INSERT con el rol de lectura debió rechazarse"
    assert rechazo.sqlstate == "42501"
    assert "linea_base" in (rechazo.diag.message_primary or "")

    with conectar("migracion", base_de_prueba) as migracion:
        assert contar(migracion, "linea_base") == 0


# --------------------------------------------------------------------------- TC-INV-3 (parte b)


def test_tkt011_car3_lectura_sin_escritura_en_las_tablas_nuevas(
    base_de_prueba: str, conectar: Conectar
) -> None:
    """TC-INV-3 (parte b) · CA-R3 · invariante 21 — la lectura no gana escritura en las siete tablas de `0007`.

    `SELECT * FROM sesion` y `SELECT password_hash FROM usuario` con el rol de lectura siguen
    respondiendo `42501`. En cada una de las siete tablas nuevas la lectura tiene exactamente
    `SELECT`, y ninguna le concede otro privilegio, ni a nivel de tabla ni de columna; las siete
    existen y le conceden `SELECT`, para que el «nada de más» no sea el de una tabla sin privilegios.
    """
    with conectar("lectura", base_de_prueba) as lectura:
        rechazos = {
            "sesion": sqlstate_de(lectura, "SELECT * FROM sesion"),
            "password_hash": sqlstate_de(lectura, "SELECT password_hash FROM usuario"),
        }

    with conectar("migracion", base_de_prueba) as migracion:
        existentes = tablas_existentes(migracion)
        de_lectura = {t: privilegios(migracion, t, "lectura") for t in TABLAS_DE_0007}
        de_tabla = migracion.execute(
            "SELECT c.relname, a.privilege_type FROM pg_class c "
            "CROSS JOIN LATERAL aclexplode(c.relacl) a "
            "JOIN pg_roles g ON g.oid = a.grantee "
            "WHERE c.relnamespace = 'public'::regnamespace AND c.relname = ANY(%s) "
            "AND g.rolname = 'cimenta_lectura' AND a.privilege_type <> 'SELECT'",
            (list(TABLAS_DE_0007),),
        ).fetchall()
        de_columna = migracion.execute(
            "SELECT t.relname, a.attname, x.privilege_type FROM pg_attribute a "
            "JOIN pg_class t ON t.oid = a.attrelid "
            "CROSS JOIN LATERAL aclexplode(a.attacl) x "
            "JOIN pg_roles g ON g.oid = x.grantee "
            "WHERE t.relnamespace = 'public'::regnamespace AND t.relname = ANY(%s) "
            "AND g.rolname = 'cimenta_lectura' AND x.privilege_type <> 'SELECT'",
            (list(TABLAS_DE_0007),),
        ).fetchall()

    assert set(TABLAS_DE_0007) <= existentes
    assert rechazos == {"sesion": "42501", "password_hash": "42501"}
    assert de_lectura == {t: {"SELECT"} for t in TABLAS_DE_0007}
    assert de_tabla == []
    assert de_columna == []
