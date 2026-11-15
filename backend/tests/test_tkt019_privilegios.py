"""TKT-019 · Privilegios y disparadores del esquema de `compras` (fila F3): TC-23 a TC-26 · CA-11.

`0014` crea siete tablas y, en la fila F3, fija quién puede hacer qué con ellas. Hay tres mecanismos
distintos y cada uno tiene su prueba:

* **Privilegios exactos por rol** (TC-23). El rol de aplicación recibe de `0001` `SELECT`, `INSERT`,
  `UPDATE` y `DELETE` sobre toda tabla nueva; la migración revoca lo que cada tabla no admite
  (`RN-04`: las solicitudes, las órdenes, las reprogramaciones y los folios no se borran). El rol de
  lectura solo tiene `SELECT`. Nadie recibe `TRUNCATE`, `REFERENCES`, `TRIGGER` ni `MAINTAIN`, y
  `PUBLIC` no recibe nada.
* **Rechazo real del motor** (TC-24). No basta con que el catálogo diga que falta el privilegio: la
  prueba intenta el `DELETE`, el `UPDATE` o el `TRUNCATE` con el rol de aplicación, espera `42501` y
  comprueba que la fila quedó idéntica.
* **Disparadores de borrado** (TC-25 y TC-26). `DELETE` sobre `requisicion` y sobre
  `requisicion_renglon` sí está concedido, porque un `BORRADOR` se borra; pero fuera de `BORRADOR` el
  disparador responde `IN002` con el nombre del disparador como `constraint_name`, para que el
  `consumido` de `RN-03` no pierda su peso. La concurrencia (TC-26) se prueba sin `sleep`: una
  transacción cambia el estado y no confirma, y el borrado del renglón debe quedar detenido en el
  `FOR SHARE` del disparador (`pg_blocking_pids`) y, al confirmar la primera, fallar con `IN002`.

Cada archivo del ticket define sus propias ayudas y no se importa de los otros. Las escrituras de datos
van con el rol de aplicación; el catálogo se lee con el de migración. Excepción declarada: la fila de
`folio_consecutivo` la escribe el rol de migración, porque el de aplicación ya no tiene `INSERT` (D-17).

Los importes y las cantidades se construyen desde cadena, nunca desde `float`.
"""

from __future__ import annotations

import itertools
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import psycopg
import pytest
from psycopg import sql
from psycopg.types.json import Jsonb

from herramientas.soporte_tkt017_entorno import Hilo
from herramientas.tiempo_de_prueba import esperar_hasta

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta. Solo mypy
    # necesita los tipos de las fábricas, y las anotaciones no se evalúan.
    from conftest import Conectar, DatosPresupuesto

Conexion = psycopg.Connection[tuple[Any, ...]]
Query = str | sql.SQL | sql.Composed

AHORA = datetime(2026, 11, 14, 9, 0, tzinfo=UTC)

APLICACION = "cimenta_aplicacion"
LECTURA = "cimenta_lectura"
MIGRACION = "cimenta_migracion"

TABLAS_COMPRAS: tuple[str, ...] = (
    "requisicion",
    "requisicion_renglon",
    "orden_compra",
    "orden_compra_renglon",
    "solicitud_autorizacion",
    "reprogramacion_entrega",
    "folio_consecutivo",
)

TRIGGER_REQUISICION = "trg_requisicion_borrado_solo_borrador"
TRIGGER_RENGLON = "trg_requisicion_renglon_borrado_solo_borrador"

LECTURA_SOLA = frozenset({"SELECT"})
LECTURA_Y_ESCRITURA = frozenset({"SELECT", "INSERT", "UPDATE"})

# Los privilegios exactos del rol de aplicación por tabla (diseño, «19 a 30 · privilegios»).
PRIVILEGIOS_DE_APLICACION: dict[str, frozenset[str]] = {
    "requisicion": frozenset({"SELECT", "INSERT", "UPDATE", "DELETE"}),
    "requisicion_renglon": frozenset({"SELECT", "INSERT", "UPDATE", "DELETE"}),
    "solicitud_autorizacion": LECTURA_Y_ESCRITURA,
    "orden_compra": LECTURA_Y_ESCRITURA,
    "orden_compra_renglon": LECTURA_Y_ESCRITURA,
    "reprogramacion_entrega": frozenset({"SELECT", "INSERT"}),
    "folio_consecutivo": frozenset({"SELECT", "UPDATE"}),
}

PRIVILEGIOS_NUNCA_CONCEDIDOS = ("TRUNCATE", "REFERENCES", "TRIGGER", "MAINTAIN")

# --------------------------------------------------------------------------- ayudas


def exigir_tabla(conexion: Conexion, tabla: str) -> None:
    """La precondición de toda prueba que escribe en una tabla de `compras`: que la migración exista."""
    fila = conexion.execute("SELECT to_regclass(%s)", (f"public.{tabla}",)).fetchone()
    assert fila is not None and fila[0] is not None, (
        f"Falta la migración 0014: la tabla `{tabla}` no existe (TKT-019, fila F2)"
    )


def insertar(conexion: Conexion, tabla: str, valores: dict[str, Any]) -> uuid.UUID:
    conexion.execute(
        sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
            sql.Identifier(tabla),
            sql.SQL(", ").join(sql.Identifier(columna) for columna in valores),
            sql.SQL(", ").join(sql.Placeholder() for _ in valores),
        ),
        list(valores.values()),
    )
    return uuid.UUID(str(valores["id"])) if "id" in valores else uuid.UUID(int=0)


def contar(conexion: Conexion, tabla: str, donde: str = "true") -> int:
    """`count(*)` de `tabla`; `donde` es un literal de la propia prueba, nunca un dato externo."""
    consulta = sql.SQL("SELECT count(*) FROM {} WHERE ").format(sql.Identifier(tabla)) + sql.SQL(
        donde
    )
    fila = conexion.execute(consulta).fetchone()
    assert fila is not None
    return int(fila[0])


def instantanea(conexion: Conexion, tabla: str) -> list[str]:
    """Todas las filas de `tabla` como texto, ordenadas: dice si "la fila sigue idéntica"."""
    filas = conexion.execute(
        sql.SQL("SELECT x::text FROM {} x ORDER BY 1").format(sql.Identifier(tabla))
    ).fetchall()
    return [str(fila[0]) for fila in filas]


def rechazo_de(
    conexion: Conexion, consulta: Query, parametros: tuple[Any, ...] = ()
) -> psycopg.Error:
    """Ejecuta `consulta` y devuelve el error del motor; si el motor la acepta, la prueba falla."""
    try:
        conexion.execute(consulta, parametros)
    except psycopg.Error as error:
        return error
    raise AssertionError(f"El motor aceptó la sentencia y debía rechazarla: {consulta!r}")


# --------------------------------------------------------------------------- fábricas

_folios = itertools.count(1)


@dataclass
class Entorno:
    """Las filas padre de las siete tablas, ya escritas, y las conexiones de los dos roles."""

    conexion: Conexion  # rol de aplicación: quien escribe en producción
    migracion: Conexion  # rol de migración: lee el catálogo y escribe lo que el otro ya no puede
    usuario: uuid.UUID
    obra: uuid.UUID
    tipo_partida: uuid.UUID
    insumo: uuid.UUID


@pytest.fixture
def entorno(
    base_de_prueba: str, conectar: Conectar, datos_presupuesto: DatosPresupuesto
) -> Entorno:
    """Un usuario, una obra, un tipo de partida y un insumo reales, escritos con el rol de aplicación.

    Solo toca tablas anteriores a `0014`: en rojo no falla aquí, falla en la aserción de la prueba.
    """
    return Entorno(
        conexion=conectar("aplicacion", base_de_prueba),
        migracion=conectar("migracion", base_de_prueba),
        usuario=datos_presupuesto.usuario(),
        obra=datos_presupuesto.obra(codigo="OB-T019"),
        tipo_partida=datos_presupuesto.tipo_partida(),
        insumo=datos_presupuesto.insumo_nuevo(),
    )


def exigir_compras(e: Entorno) -> None:
    for tabla in TABLAS_COMPRAS:
        exigir_tabla(e.conexion, tabla)


def fila_requisicion(e: Entorno, **cambios: Any) -> dict[str, Any]:
    """Una requisición `EVALUADA` con folio único que cumple todo; `cambios` pisa columnas."""
    valores: dict[str, Any] = {
        "id": uuid.uuid4(),
        "folio": f"REQ-{next(_folios):04d}",
        "obra_id": e.obra,
        "tipo_partida_id": e.tipo_partida,
        "solicitante_id": e.usuario,
        "estado": "EVALUADA",
        "importe_solicitado": Decimal("8000.0000"),
        "creado_en": AHORA,
        "actualizado_en": AHORA,
    }
    valores.update(cambios)
    return valores


def fila_requisicion_renglon(
    e: Entorno, requisicion_id: uuid.UUID, **cambios: Any
) -> dict[str, Any]:
    valores: dict[str, Any] = {
        "id": uuid.uuid4(),
        "requisicion_id": requisicion_id,
        "insumo_id": e.insumo,
        "cantidad": Decimal("10.0000"),
        "costo_unitario_estimado": Decimal("800.0000"),
        "importe": Decimal("8000.0000"),
    }
    valores.update(cambios)
    return valores


def fila_orden(e: Entorno, requisicion_id: uuid.UUID, **cambios: Any) -> dict[str, Any]:
    """Una orden viva; `proveedor_id` no existe en ninguna tabla: no tiene clave foránea."""
    valores: dict[str, Any] = {
        "id": uuid.uuid4(),
        "folio": f"OC-{next(_folios):04d}",
        "requisicion_id": requisicion_id,
        "obra_id": e.obra,
        "proveedor_id": uuid.uuid4(),
        "importe": Decimal("8000.0000"),
        "creado_en": AHORA,
    }
    valores.update(cambios)
    return valores


def fila_orden_renglon(e: Entorno, orden_id: uuid.UUID, **cambios: Any) -> dict[str, Any]:
    """Sin `cantidad_recibida` ni `cantidad_excedente_autorizada`: lo decide el motor (`DEFAULT 0`)."""
    valores: dict[str, Any] = {
        "id": uuid.uuid4(),
        "orden_compra_id": orden_id,
        "insumo_id": e.insumo,
        "cantidad_ordenada": Decimal("10.0000"),
        "fecha_compromiso": date(2026, 11, 20),
        "costo_unitario": Decimal("800.0000"),
        "importe": Decimal("8000.0000"),
    }
    valores.update(cambios)
    return valores


def fila_solicitud(e: Entorno, **cambios: Any) -> dict[str, Any]:
    """Una solicitud `PENDIENTE` por `EXCEDE_PRESUPUESTO` sobre una requisición cualquiera."""
    valores: dict[str, Any] = {
        "id": uuid.uuid4(),
        "motivo": "EXCEDE_PRESUPUESTO",
        "entidad_tipo": "REQUISICION",
        "entidad_id": uuid.uuid4(),
        "obra_id": e.obra,
        "regla_negocio": "RN-03",
        "solicitante_id": e.usuario,
        "rol_autorizador": "DIRECCION_GENERAL",
        "estado": "PENDIENTE",
        "contexto": Jsonb({"disponible": "12000.0000"}),
        "creado_en": AHORA,
    }
    valores.update(cambios)
    return valores


def fila_reprogramacion(e: Entorno, renglon_id: uuid.UUID, **cambios: Any) -> dict[str, Any]:
    valores: dict[str, Any] = {
        "id": uuid.uuid4(),
        "orden_compra_renglon_id": renglon_id,
        "fecha_anterior": date(2026, 11, 20),
        "fecha_nueva": date(2026, 11, 27),
        "saldo_pendiente": Decimal("5.0000"),
        "motivo": "El proveedor aplazó la entrega.",
        "registrado_por_id": e.usuario,
        "ocurrido_en": AHORA,
    }
    valores.update(cambios)
    return valores


@dataclass
class Documentos:
    """Una fila de cada una de las siete tablas, con la clave que la identifica."""

    claves: dict[str, Any]


# La columna de la clave primaria de cada tabla: `folio_consecutivo` se identifica por su serie.
COLUMNA_CLAVE: dict[str, str] = {tabla: "id" for tabla in TABLAS_COMPRAS} | {
    "folio_consecutivo": "serie"
}


@pytest.fixture
def documentos(entorno: Entorno) -> Documentos:
    """Una fila en cada tabla de `compras`, escrita con el rol de aplicación.

    La de `folio_consecutivo` la escribe el rol de migración (el de aplicación ya no tiene `INSERT`)
    y es idempotente: la siembra de `0015` ya la deja, y el `ON CONFLICT` evita duplicarla.
    """
    exigir_compras(entorno)
    e = entorno
    requisicion = insertar(e.conexion, "requisicion", fila_requisicion(e))
    insertar(e.conexion, "requisicion_renglon", fila_requisicion_renglon(e, requisicion))
    orden = insertar(e.conexion, "orden_compra", fila_orden(e, requisicion))
    renglon = insertar(e.conexion, "orden_compra_renglon", fila_orden_renglon(e, orden))
    solicitud = insertar(e.conexion, "solicitud_autorizacion", fila_solicitud(e))
    reprogramacion = insertar(e.conexion, "reprogramacion_entrega", fila_reprogramacion(e, renglon))
    e.migracion.execute(
        "INSERT INTO folio_consecutivo (serie, ultimo) VALUES ('REQUISICION', 0) "
        "ON CONFLICT (serie) DO NOTHING"
    )
    return Documentos(
        claves={
            "requisicion": requisicion,
            "orden_compra": orden,
            "orden_compra_renglon": renglon,
            "solicitud_autorizacion": solicitud,
            "reprogramacion_entrega": reprogramacion,
            "folio_consecutivo": "REQUISICION",
        }
    )


# --------------------------------------------------------------------------- TC-23


def _privilegios_concedidos(e: Entorno) -> dict[tuple[str, str], set[str]]:
    """`(tabla, titular) → privilegios` según `aclexplode(relacl)`; `PUBLIC` aparece como tal."""
    filas = e.migracion.execute(
        "SELECT c.relname, CASE a.grantee WHEN 0 THEN 'PUBLIC' ELSE a.grantee::regrole::text END, "
        "a.privilege_type "
        "FROM pg_class c "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "CROSS JOIN LATERAL aclexplode(c.relacl) a "
        "WHERE n.nspname = 'public' AND c.relname = ANY(%s)",
        (list(TABLAS_COMPRAS),),
    ).fetchall()
    concedidos: dict[tuple[str, str], set[str]] = {}
    for tabla, titular, privilegio in filas:
        concedidos.setdefault((str(tabla), str(titular)), set()).add(str(privilegio))
    return concedidos


def test_tkt019_ca11_privilegios_exactos_por_rol(entorno: Entorno) -> None:
    """TC-23 · CA-11 · RN-04 — cada rol tiene exactamente los privilegios del diseño en las siete tablas.

    El rol de aplicación, `{SELECT, INSERT, UPDATE, DELETE}` en `requisicion` y su renglón;
    `{SELECT, INSERT, UPDATE}` en la solicitud, la orden y su renglón; `{SELECT, INSERT}` en la
    reprogramación; `{SELECT, UPDATE}` en `folio_consecutivo`. El de lectura, `{SELECT}` en las siete.
    `PUBLIC` no tiene nada, y ni la aplicación ni la lectura reciben `TRUNCATE`, `REFERENCES`,
    `TRIGGER` ni `MAINTAIN`: `has_table_privilege` también cuenta lo heredado de `PUBLIC`. Las
    diferencias se acumulan para que un solo fallo las muestre todas.
    """
    exigir_compras(entorno)
    concedidos = _privilegios_concedidos(entorno)
    problemas: list[str] = []

    for tabla in TABLAS_COMPRAS:
        esperados = {
            APLICACION: PRIVILEGIOS_DE_APLICACION[tabla],
            LECTURA: LECTURA_SOLA,
        }
        for rol, esperado in esperados.items():
            obtenido = frozenset(concedidos.get((tabla, rol), set()))
            if obtenido != esperado:
                problemas.append(
                    f"{tabla} · {rol}: tiene {sorted(obtenido)}, debía tener {sorted(esperado)} "
                    f"(sobra {sorted(obtenido - esperado)}, falta {sorted(esperado - obtenido)})"
                )
        if (tabla, "PUBLIC") in concedidos:
            problemas.append(f"{tabla} · PUBLIC: tiene {sorted(concedidos[(tabla, 'PUBLIC')])}")
        otros = {titular for (t, titular) in concedidos if t == tabla} - {
            MIGRACION,
            APLICACION,
            LECTURA,
            "PUBLIC",
        }
        if otros:
            problemas.append(f"{tabla}: privilegios para titulares inesperados {sorted(otros)}")
        for rol in (APLICACION, LECTURA):
            for privilegio in PRIVILEGIOS_NUNCA_CONCEDIDOS:
                fila = entorno.migracion.execute(
                    "SELECT has_table_privilege(%s, %s, %s)", (rol, f"public.{tabla}", privilegio)
                ).fetchone()
                assert fila is not None
                if fila[0]:
                    problemas.append(f"{tabla} · {rol}: tiene {privilegio} y no debe")

    assert not problemas, "Privilegios que no son los del diseño:\n" + "\n".join(problemas)


# --------------------------------------------------------------------------- TC-24

# (operación, tabla): lo que el rol de aplicación no puede hacer sobre lo permanente (RN-04).
# El diseño enumera cinco `DELETE`, un `UPDATE` y los siete `TRUNCATE`.
NO_PERMITIDO: tuple[tuple[str, str], ...] = (
    ("DELETE", "solicitud_autorizacion"),
    ("DELETE", "reprogramacion_entrega"),
    ("DELETE", "orden_compra"),
    ("DELETE", "orden_compra_renglon"),
    ("DELETE", "folio_consecutivo"),
    ("UPDATE", "reprogramacion_entrega"),
    *(("TRUNCATE", tabla) for tabla in TABLAS_COMPRAS),
)


def _sentencia(operacion: str, tabla: str) -> Query:
    """La sentencia de `operacion` sobre la fila de `tabla` (o sobre toda la tabla, en `TRUNCATE`)."""
    objeto = sql.Identifier(tabla)
    if operacion == "TRUNCATE":
        return sql.SQL("TRUNCATE {}").format(objeto)
    clave = sql.Identifier(COLUMNA_CLAVE[tabla])
    if operacion == "DELETE":
        return sql.SQL("DELETE FROM {} WHERE {} = %s").format(objeto, clave)
    return sql.SQL("UPDATE {} SET motivo = 'Cambio indebido.' WHERE {} = %s").format(objeto, clave)


@pytest.mark.parametrize(
    ("operacion", "tabla"), NO_PERMITIDO, ids=[f"{op}-{tabla}" for op, tabla in NO_PERMITIDO]
)
def test_tkt019_ca11_el_rol_de_aplicacion_no_borra_lo_permanente(
    entorno: Entorno, documentos: Documentos, operacion: str, tabla: str
) -> None:
    """TC-24 · CA-11 · RN-04 — `DELETE`, `UPDATE` y `TRUNCATE` sobre lo permanente responden `42501`.

    Con el rol de aplicación y una fila real en cada tabla: la solicitud, la reprogramación, la orden
    y su renglón y el folio no se borran; la reprogramación tampoco se actualiza (es un asiento); y
    ninguna de las siete tablas se vacía con `TRUNCATE`. El motor responde `42501` nombrando la tabla,
    y la tabla queda idéntica (`SELECT t::text`). El rechazo viene del privilegio, no de un disparador:
    un `TRUNCATE` no dispara disparadores de fila.
    """
    consulta = _sentencia(operacion, tabla)
    parametros: tuple[Any, ...] = () if operacion == "TRUNCATE" else (documentos.claves[tabla],)
    antes = instantanea(entorno.conexion, tabla)
    assert antes, f"La prueba necesita una fila en {tabla} para comprobar que sigue igual"

    error = rechazo_de(entorno.conexion, consulta, parametros)

    assert error.sqlstate == "42501", str(error)
    assert f"permission denied for table {tabla}" in str(error), str(error)
    assert instantanea(entorno.conexion, tabla) == antes, "El rechazo no debe cambiar ninguna fila"


# --------------------------------------------------------------------------- TC-25

ESTADOS_NO_BORRABLES = (
    "EVALUADA",
    "BLOQUEADA",
    "AUTORIZADA",
    "RECHAZADA",
    "CANCELADA",
    "CONVERTIDA",
)


def _requisicion_en(e: Entorno, estado: str) -> uuid.UUID:
    """Una requisición en `estado` que cumple sus `CHECK`: sin folio en `BORRADOR`, con motivo si se cancela."""
    cambios: dict[str, Any] = {"estado": estado}
    if estado == "BORRADOR":
        cambios["folio"] = None
    if estado == "CANCELADA":
        cambios["motivo_cancelacion"] = "La obra cambió de alcance."
    return insertar(e.conexion, "requisicion", fila_requisicion(e, **cambios))


@pytest.mark.parametrize("estado", ESTADOS_NO_BORRABLES)
def test_tkt019_ca11_solo_se_borra_un_borrador(entorno: Entorno, estado: str) -> None:
    """TC-25 · CA-11 · RN-03 — fuera de `BORRADOR`, ni la requisición ni su renglón se borran (`IN002`).

    Una requisición viva consume (`RN-03`: una `EVALUADA` sí consume), así que borrarla devolvería su
    importe al disponible. Con el rol de aplicación, que sí tiene `DELETE` en las dos tablas:

    * `DELETE` del renglón de una requisición en `estado` → `IN002`, `constraint_name` =
      `trg_requisicion_renglon_borrado_solo_borrador`, y el mensaje dice la requisición y su estado;
    * `DELETE` de otra requisición en `estado`, sin renglones → `IN002`,
      `trg_requisicion_borrado_solo_borrador`.

    En los dos casos la fila sigue ahí. Sin los disparadores (`M-11`, `M-12`) el motor la borra.
    """
    exigir_compras(entorno)
    con_renglon = _requisicion_en(entorno, estado)
    renglon = insertar(
        entorno.conexion,
        "requisicion_renglon",
        fila_requisicion_renglon(entorno, con_renglon),
    )
    sin_renglones = _requisicion_en(entorno, estado)
    renglones_antes = instantanea(entorno.conexion, "requisicion_renglon")
    requisiciones_antes = instantanea(entorno.conexion, "requisicion")

    sobre_el_renglon = rechazo_de(
        entorno.conexion, "DELETE FROM requisicion_renglon WHERE id = %s", (renglon,)
    )
    assert sobre_el_renglon.sqlstate == "IN002", str(sobre_el_renglon)
    assert sobre_el_renglon.diag.constraint_name == TRIGGER_RENGLON, str(sobre_el_renglon)
    assert sobre_el_renglon.diag.table_name == "requisicion_renglon", str(sobre_el_renglon)
    assert sobre_el_renglon.diag.schema_name == "public", str(sobre_el_renglon)
    mensaje = sobre_el_renglon.diag.message_primary or ""
    assert str(con_renglon) in mensaje, mensaje
    assert estado in mensaje, mensaje
    assert instantanea(entorno.conexion, "requisicion_renglon") == renglones_antes

    sobre_la_requisicion = rechazo_de(
        entorno.conexion, "DELETE FROM requisicion WHERE id = %s", (sin_renglones,)
    )
    assert sobre_la_requisicion.sqlstate == "IN002", str(sobre_la_requisicion)
    assert sobre_la_requisicion.diag.constraint_name == TRIGGER_REQUISICION, str(
        sobre_la_requisicion
    )
    assert sobre_la_requisicion.diag.table_name == "requisicion", str(sobre_la_requisicion)
    assert sobre_la_requisicion.diag.schema_name == "public", str(sobre_la_requisicion)
    mensaje = sobre_la_requisicion.diag.message_primary or ""
    assert str(sin_renglones) in mensaje, mensaje
    assert estado in mensaje, mensaje
    assert instantanea(entorno.conexion, "requisicion") == requisiciones_antes


def test_tkt019_ca11_un_borrador_se_borra_con_sus_renglones(entorno: Entorno) -> None:
    """TC-25 (control) · CA-11 — un `BORRADOR` sí se borra: primero sus renglones y después la requisición.

    Sin este control, un disparador que rechaza todo —o un privilegio `DELETE` revocado— pasaría las
    pruebas de rechazo. El `BORRADOR` no tiene folio todavía (`ck_requisicion_folio_fuera_de_borrador`).
    Una segunda requisición `EVALUADA` con su renglón prueba que el borrado no tocó nada más.
    """
    exigir_compras(entorno)
    borrador = _requisicion_en(entorno, "BORRADOR")
    for _ in range(2):
        insertar(
            entorno.conexion, "requisicion_renglon", fila_requisicion_renglon(entorno, borrador)
        )
    viva = _requisicion_en(entorno, "EVALUADA")
    renglon_vivo = insertar(
        entorno.conexion, "requisicion_renglon", fila_requisicion_renglon(entorno, viva)
    )
    assert contar(entorno.conexion, "requisicion_renglon", f"requisicion_id = '{borrador}'") == 2

    entorno.conexion.execute(
        "DELETE FROM requisicion_renglon WHERE requisicion_id = %s", (borrador,)
    )
    entorno.conexion.execute("DELETE FROM requisicion WHERE id = %s", (borrador,))

    assert contar(entorno.conexion, "requisicion", f"id = '{borrador}'") == 0
    assert contar(entorno.conexion, "requisicion_renglon", f"requisicion_id = '{borrador}'") == 0
    assert contar(entorno.conexion, "requisicion", f"id = '{viva}'") == 1
    assert contar(entorno.conexion, "requisicion_renglon", f"id = '{renglon_vivo}'") == 1


# --------------------------------------------------------------------------- TC-26


def _alguien_borra_renglones_y_espera(observador: Conexion) -> bool:
    """Una sesión de la base detenida por un bloqueo, con un `DELETE` de `requisicion_renglon`."""
    fila = observador.execute(
        "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() "
        "AND wait_event_type = 'Lock' AND cardinality(pg_blocking_pids(pid)) > 0 "
        "AND query ILIKE %s",
        ("%DELETE FROM requisicion_renglon%",),
    ).fetchone()
    assert fila is not None
    return bool(fila[0])


def test_tkt019_ca11_el_borrado_del_renglon_espera_al_cambio_de_estado(
    base_de_prueba: str, conectar: Conectar, entorno: Entorno
) -> None:
    """TC-26 · CA-11 · RN-03 — el borrado del renglón espera a que se confirme el cambio de estado.

    Sin `sleep`. La transacción A, con el rol de aplicación, pasa la requisición de `BORRADOR` a
    `EVALUADA` con folio y no confirma. El hilo B, con otra conexión del mismo rol, intenta borrar el
    renglón: el disparador lee el estado con `SELECT ... FOR SHARE` y debe quedar detenido
    (`wait_event_type = 'Lock'` y `pg_blocking_pids` no vacío en `pg_stat_activity`) mientras A no
    confirma. Al confirmar A, B lee el estado confirmado y falla con `IN002` sobre
    `trg_requisicion_renglon_borrado_solo_borrador`: el mensaje dice `EVALUADA`, y el renglón sigue.
    Sin `FOR SHARE` (`M-13`) B lee el estado viejo, no espera y borra un renglón de una requisición que
    ya consume.
    """
    exigir_compras(entorno)
    requisicion = _requisicion_en(entorno, "BORRADOR")
    renglon = insertar(
        entorno.conexion, "requisicion_renglon", fila_requisicion_renglon(entorno, requisicion)
    )
    transaccion_a = conectar("aplicacion", base_de_prueba, autocommit=False)
    conexion_b = conectar("aplicacion", base_de_prueba)

    def borrar_el_renglon() -> None:
        conexion_b.execute(
            "DELETE FROM requisicion_renglon WHERE requisicion_id = %s", (requisicion,)
        )

    b = Hilo("B", borrar_el_renglon)
    try:
        transaccion_a.execute(
            "UPDATE requisicion SET estado = 'EVALUADA', folio = 'REQ-9001' WHERE id = %s",
            (requisicion,),
        )
        b.start()
        # Termina cuando B queda detenido o, si el borrado no espera, cuando B ya acabó: así el rojo
        # no gasta el límite entero. La afirmación de abajo distingue los dos casos.
        esperar_hasta(
            lambda: _alguien_borra_renglones_y_espera(entorno.conexion) or not b.is_alive(), 5.0
        )
        assert b.is_alive() and _alguien_borra_renglones_y_espera(entorno.conexion), (
            "B debía quedar esperando a que A confirme el cambio de estado (FOR SHARE del "
            f"disparador): terminó sin esperar con {b.error!r}"
        )
        assert contar(entorno.conexion, "requisicion_renglon", f"id = '{renglon}'") == 1
    finally:
        transaccion_a.commit()
        if b.ident is not None:
            b.terminar()

    error = b.error
    assert isinstance(error, psycopg.Error), f"B debía fallar con un error del motor: {error!r}"
    assert error.sqlstate == "IN002", str(error)
    assert error.diag.constraint_name == TRIGGER_RENGLON, str(error)
    assert error.diag.table_name == "requisicion_renglon", str(error)
    mensaje = error.diag.message_primary or ""
    assert str(requisicion) in mensaje, mensaje
    assert "EVALUADA" in mensaje, mensaje
    assert contar(entorno.conexion, "requisicion_renglon", f"id = '{renglon}'") == 1
    assert (
        contar(entorno.conexion, "requisicion", f"id = '{requisicion}' AND estado = 'EVALUADA'")
        == 1
    )
