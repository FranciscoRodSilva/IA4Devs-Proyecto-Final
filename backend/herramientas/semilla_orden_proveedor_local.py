"""Siembra en la base local una orden de compra `PARCIAL` contra un proveedor ya dado de alta (TKT-032a, H-2).

Se invoca desde backend/ con:
uv run --env-file ../.env python -m herramientas.semilla_orden_proveedor_local

Es apoyo de pruebas: prepara datos para el E2E de la baja con órdenes pendientes (CA-8 de TKT-032a) y
para la demostración en local. No es código de producto: ningún módulo de `cimenta/` la importa.

Solo escribe en la base local: `exigir_base_local()` niega cualquier host que no sea 127.0.0.1, localhost
o ::1, y las variables `PGHOSTADDR` y `PGSERVICE`, antes de abrir ninguna conexión. Se conecta con el rol
de aplicación, igual que la aplicación. La orden la escribe `sembrar_orden_compra` de
`herramientas.soporte_tkt029b_ordenes`, que no abre transacción ni confirma: aquí se resuelven los
identificadores por SQL parametrizado, se siembra dentro de una sola transacción y se confirma con
`commit()` explícito; si algo falla, se deshace todo con `rollback()`.

Variables obligatorias, sin valor por omisión: `CIMENTA_SEMILLA_OC_RFC` (el RFC del proveedor, que debe
existir), `CIMENTA_SEMILLA_OC_OBRA_ID` (el identificador de la obra) y `CIMENTA_SEMILLA_OC_CORREO` (el
correo del solicitante, que debe existir). Las claves `MUROS` y el insumo `MO-001` los deja
`herramientas.semilla_linea_base_local`, así que esa semilla debe haberse ejecutado antes en la base.

El folio es `OC-E2E-<8 hex>` y es único por corrida, porque `uq_orden_compra_folio` y
`uq_requisicion_folio` romperían una segunda ejecución sobre la base acumulativa. La orden lleva un solo
renglón, de 10 unidades ordenadas y 4 recibidas, así que queda `PARCIAL`.

La salida tiene `FOLIO=<folio>` y, como última línea, `ORDEN_ID=<uuid>`, que lee la ayuda del E2E.
"""

import os
import uuid
from typing import Any, Final

import psycopg
from sqlalchemy import Engine

from cimenta.proveedores.dominio.proveedor import normalizar_rfc
from herramientas.conexion import crear_motor_aplicacion
from herramientas.semilla_local import exigir_base_local
from herramientas.soporte_tkt029b_ordenes import sembrar_orden_compra

VARIABLE_RFC: Final = "CIMENTA_SEMILLA_OC_RFC"
VARIABLE_OBRA_ID: Final = "CIMENTA_SEMILLA_OC_OBRA_ID"
VARIABLE_CORREO: Final = "CIMENTA_SEMILLA_OC_CORREO"
CLAVE_MUROS: Final = "MUROS"
CODIGO_MANO_DE_OBRA: Final = "MO-001"
PREFIJO_FOLIO: Final = "OC-E2E-"
# Un renglón: 10 ordenadas, 4 recibidas. Con saldo y algo recibido, la orden queda PARCIAL.
RENGLONES: Final[tuple[tuple[str, str], ...]] = (("10.0000", "4.0000"),)

Conexion = psycopg.Connection[tuple[Any, ...]]


def _variable(nombre: str) -> str:
    """Devuelve la variable `nombre` sin espacios; si falta o está vacía, sale nombrándola."""
    valor = os.environ.get(nombre, "").strip()
    if not valor:
        raise SystemExit(
            f"Falta la variable de entorno {nombre}. No se ha conectado ni escrito nada."
        )
    return valor


def _buscar_id(
    conexion: Conexion, consulta: str, parametros: tuple[Any, ...], mensaje: str
) -> uuid.UUID:
    """Ejecuta una consulta parametrizada que devuelve un `id`; si no hay fila, sale con `mensaje`."""
    fila = conexion.execute(consulta, parametros).fetchone()
    if fila is None:
        raise SystemExit(f"{mensaje} No se ha escrito nada.")
    return uuid.UUID(str(fila[0]))


def _folio_nuevo() -> str:
    return PREFIJO_FOLIO + uuid.uuid4().hex[:8]


def _sembrar(
    conexion: Conexion, *, rfc: str, obra_id: uuid.UUID, correo: str
) -> tuple[str, uuid.UUID]:
    """Resuelve los identificadores y siembra la orden dentro de la transacción de `conexion`.

    No confirma: quien llama decide el `commit()` o el `rollback()`. Devuelve el folio y el `id` de la orden.
    """
    proveedor_id = _buscar_id(
        conexion,
        "SELECT id FROM proveedor WHERE rfc = %s",
        (normalizar_rfc(rfc),),
        f"No existe ningún proveedor con el RFC {rfc}; dalo de alta antes de sembrar la orden.",
    )
    _buscar_id(
        conexion,
        "SELECT id FROM obra WHERE id = %s",
        (obra_id,),
        f"No existe la obra {obra_id}.",
    )
    solicitante_id = _buscar_id(
        conexion,
        "SELECT id FROM usuario WHERE email = %s",
        (correo.lower(),),
        f"Falta el usuario {correo}; ejecuta herramientas.semilla_local.",
    )
    tipo_partida_id = _buscar_id(
        conexion,
        "SELECT id FROM tipo_partida WHERE clave = %s",
        (CLAVE_MUROS,),
        f"Falta el tipo de partida {CLAVE_MUROS}; ejecuta herramientas.semilla_linea_base_local.",
    )
    insumo_id = _buscar_id(
        conexion,
        "SELECT id FROM insumo WHERE codigo = %s",
        (CODIGO_MANO_DE_OBRA,),
        f"Falta el insumo {CODIGO_MANO_DE_OBRA}; ejecuta herramientas.semilla_linea_base_local.",
    )
    folio = _folio_nuevo()
    orden_id = sembrar_orden_compra(
        conexion,
        obra_id=obra_id,
        tipo_partida_id=tipo_partida_id,
        insumo_id=insumo_id,
        solicitante_id=solicitante_id,
        proveedor_id=proveedor_id,
        folio=folio,
        renglones=RENGLONES,
    )
    return folio, orden_id


def sembrar_orden_parcial(
    motor: Engine, *, rfc: str, obra_id: uuid.UUID, correo: str
) -> tuple[str, uuid.UUID]:
    """Siembra y confirma la orden en una sola transacción; devuelve el folio y el `id` de la orden.

    Toma la conexión del motor de la aplicación y la confirma con `commit()`. Si la siembra falla por una
    regla de la base o por una búsqueda, la transacción se deshace entera y la excepción sale hacia
    `main`, que la traduce a una salida distinta de cero.
    """
    crudo = motor.raw_connection()
    try:
        conexion = crudo.driver_connection
        if conexion is None:
            raise SystemExit("La conexión a la base no está disponible. No se ha escrito nada.")
        try:
            resultado = _sembrar(conexion, rfc=rfc, obra_id=obra_id, correo=correo)
            conexion.commit()
        except BaseException:
            conexion.rollback()
            raise
    finally:
        crudo.close()
    return resultado


def main() -> int:
    """Punto de entrada: niega fuera de la base local, siembra la orden y deja `ORDEN_ID=` en la última línea."""
    try:
        exigir_base_local()
    except RuntimeError as error:
        raise SystemExit(str(error)) from None
    rfc = _variable(VARIABLE_RFC)
    obra_texto = _variable(VARIABLE_OBRA_ID)
    correo = _variable(VARIABLE_CORREO)
    try:
        obra_id = uuid.UUID(obra_texto)
    except ValueError:
        raise SystemExit(
            f"{VARIABLE_OBRA_ID} no es un identificador uuid. No se ha conectado ni escrito nada."
        ) from None
    try:
        motor = crear_motor_aplicacion()
    except RuntimeError as error:
        raise SystemExit(str(error)) from None
    except ValueError:
        raise SystemExit(
            "Negado: CIMENTA_DB_PUERTO no es un número entero. No se ha conectado."
        ) from None
    try:
        folio, orden_id = sembrar_orden_parcial(motor, rfc=rfc, obra_id=obra_id, correo=correo)
    except psycopg.Error as error:
        raise SystemExit(
            f"No se pudo sembrar la orden: {str(error).strip()} No se ha escrito nada."
        ) from None
    finally:
        motor.dispose()
    print(f"FOLIO={folio}")
    print(f"ORDEN_ID={orden_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
