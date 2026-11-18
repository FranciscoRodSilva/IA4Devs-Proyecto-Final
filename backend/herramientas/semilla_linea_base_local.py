"""Siembra en la base local una obra de demostración con su línea base `BORRADOR` (TKT-018a, CA-S1, Should).

Se invoca desde backend/ con:
uv run --env-file ../.env python -m herramientas.semilla_linea_base_local

Es preparación de datos para la prueba E2E y para la demostración en local. Solo escribe en la base
local: `exigir_base_local()` niega cualquier host que no sea 127.0.0.1, localhost o ::1, y las variables
`PGHOSTADDR` y `PGSERVICE`, antes de abrir ninguna conexión. Se conecta con el rol de aplicación, igual
que la aplicación, y la línea base la crea el caso de uso `materializar_importacion` de la interfaz
publicada de `presupuesto`; la semilla solo prepara la obra, el insumo de mano de obra y la importación
confirmable.

Variables: `CIMENTA_SEMILLA_LB_CODIGO` (por omisión `DEMO-018A`) y `CIMENTA_SEMILLA_LB_CORREO` (por
omisión `director_proyectos@cimenta.test`, el usuario que siembra `herramientas.semilla_local`). La última
línea de la salida es `OBRA_ID=<uuid>`, que lee la preparación del E2E.

Con la bandera `--congelar` (TKT-012b, fila B5, TC-80) la semilla congela la línea base que acaba de
materializar con el caso de uso `congelar_linea_base`: la obra queda `ACTIVA` con su línea base
`CONGELADA`. Sin la bandera, queda `PLANEACION` con `BORRADOR`, como antes. Si el congelado se niega, la
semilla sale con `SystemExit` que empieza por «No se pudo congelar» y nombra el código de la obra, sin
imprimir `OBRA_ID=`; la obra queda `PLANEACION` con su `BORRADOR` (la transacción del congelado no
escribe nada si falla).
"""

import argparse
import json
import os
import sys
import uuid
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Final

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import sessionmaker

from cimenta.presupuesto.aplicacion.congelado import congelar_linea_base
from cimenta.presupuesto.infraestructura.preparacion_json import preparacion_a_json
from cimenta.presupuesto.interfaz import ContextoPresupuesto, materializar_importacion
from contrato_error import ErrorContrato
from herramientas.conexion import crear_motor_aplicacion
from herramientas.semilla_local import exigir_base_local
from herramientas.soporte_tkt017 import preparacion_sintetica

VARIABLE_CODIGO: Final = "CIMENTA_SEMILLA_LB_CODIGO"
CODIGO_POR_OMISION: Final = "DEMO-018A"
VARIABLE_CORREO: Final = "CIMENTA_SEMILLA_LB_CORREO"
CORREO_POR_OMISION: Final = "director_proyectos@cimenta.test"
MOTIVO_CONGELADO: Final = "Congelado de la obra de demostración para la prueba de humo"

CLAVE_MUROS: Final = "MUROS"
CLAVE_PLAFON: Final = "PLAFONES_Y_CAJILLOS"
# Mismo texto que `Entorno.registrar_mano_obra` en `soporte_tkt017_entorno.py`: la resolución por
# descripción de `preparacion_sintetica()` lo encuentra por ahí.
INSUMO_MANO_DE_OBRA: Final = "MO-001"
DESCRIPCION_MANO_DE_OBRA: Final = "OFICIAL TABLAROQUERO"


def _reloj_del_sistema() -> datetime:
    return datetime.now(UTC)


def _existe_obra(conexion: Connection, codigo: str) -> bool:
    fila = conexion.execute(text("SELECT 1 FROM obra WHERE codigo = :codigo"), {"codigo": codigo})
    return fila.first() is not None


def _empresa_activa(conexion: Connection) -> uuid.UUID:
    fila = conexion.execute(text("SELECT id FROM empresa WHERE activa ORDER BY id LIMIT 1")).first()
    if fila is None:
        raise SystemExit(
            "No hay empresa activa en la base; ejecuta las migraciones. No se ha escrito nada."
        )
    return uuid.UUID(str(fila[0]))


def _tipo_partida(conexion: Connection, clave: str) -> uuid.UUID:
    fila = conexion.execute(
        text("SELECT id FROM tipo_partida WHERE clave = :clave"), {"clave": clave}
    ).one()
    return uuid.UUID(str(fila[0]))


def _insertar_obra(
    conexion: Connection,
    *,
    obra_id: uuid.UUID,
    empresa_id: uuid.UUID,
    codigo: str,
    usuario_id: uuid.UUID,
) -> None:
    conexion.execute(
        text(
            "INSERT INTO obra (id, empresa_id, codigo, nombre, domicilio, tipo_contrato, "
            "retencion_destajo_pct, fondo_garantia_pct, iva_acreditable, estado, creado_por_id) "
            "VALUES (:id, :empresa_id, :codigo, :nombre, 'Semilla local', "
            "'PRECIO_ALZADO_MAXIMO_GARANTIZADO', :retencion, :fondo, true, 'PLANEACION', :usuario_id)"
        ),
        {
            "id": obra_id,
            "empresa_id": empresa_id,
            "codigo": codigo,
            "nombre": f"Obra de demostracion {codigo}",
            "retencion": "0.050000",
            "fondo": "0.050000",
            "usuario_id": usuario_id,
        },
    )


def _insertar_mano_de_obra(conexion: Connection) -> None:
    conexion.execute(
        text(
            "INSERT INTO insumo (id, codigo, descripcion, tipo, unidad, activo, creado_en_importacion) "
            "VALUES (:id, :codigo, :descripcion, 'MANO_OBRA', 'JORNAL', true, false) "
            "ON CONFLICT DO NOTHING"
        ),
        {
            "id": uuid.uuid4(),
            "codigo": INSUMO_MANO_DE_OBRA,
            "descripcion": DESCRIPCION_MANO_DE_OBRA,
        },
    )


def _insertar_importacion(
    conexion: Connection,
    *,
    importacion_id: uuid.UUID,
    obra_id: uuid.UUID,
    usuario_id: uuid.UUID,
) -> None:
    # `archivo_id` es lógico (sin clave foránea, CA-7): la semilla no crea ningún archivo.
    preparacion = json.dumps(preparacion_a_json(preparacion_sintetica()))
    conexion.execute(
        text(
            "INSERT INTO importacion (id, obra_id, archivo_id, estado, importado_por_id, preparacion) "
            "VALUES (:id, :obra_id, :archivo_id, 'VALIDADO', :usuario_id, CAST(:preparacion AS jsonb))"
        ),
        {
            "id": importacion_id,
            "obra_id": obra_id,
            "archivo_id": uuid.uuid4(),
            "usuario_id": usuario_id,
            "preparacion": preparacion,
        },
    )


def sembrar_linea_base(
    motor: Engine,
    *,
    codigo: str,
    usuario_id: uuid.UUID,
    reloj: Callable[[], datetime],
    congelar: bool = False,
) -> uuid.UUID:
    """Siembra la obra `codigo` en `PLANEACION` y confirma su importación; devuelve el `obra_id`.

    La primera transacción prepara las filas y comprueba que el código no exista; si existe, sale con
    `SystemExit` y no escribe nada. La confirmación es un caso de uso propio, con su transacción y su
    bitácora, así que va fuera de la anterior. Con `congelar=True` congela después la línea base
    materializada, con su propia transacción y su asiento `CONGELAR` (RN-01).
    """
    obra_id = uuid.uuid4()
    importacion_id = uuid.uuid4()
    with motor.begin() as conexion:
        if _existe_obra(conexion, codigo):
            raise SystemExit(f"Ya existe la obra {codigo}; usa otro codigo. No se ha escrito nada.")
        empresa_id = _empresa_activa(conexion)
        _insertar_obra(
            conexion, obra_id=obra_id, empresa_id=empresa_id, codigo=codigo, usuario_id=usuario_id
        )
        _insertar_mano_de_obra(conexion)
        _insertar_importacion(
            conexion, importacion_id=importacion_id, obra_id=obra_id, usuario_id=usuario_id
        )
        muros = _tipo_partida(conexion, CLAVE_MUROS)
        plafon = _tipo_partida(conexion, CLAVE_PLAFON)

    contexto = ContextoPresupuesto(
        fabrica_sesiones=lambda: sessionmaker(bind=motor, expire_on_commit=False),
        reloj=reloj,
    )
    materializada = materializar_importacion(
        contexto,
        importacion_id=importacion_id,
        asignacion_tipos_partida={"MUROS EXTERIORES": muros, "PLAFON": plafon},
        reemplazar_borrador=False,
        motivo_reemplazo=None,
        usuario_id=usuario_id,
    )
    if congelar:
        _congelar(
            contexto,
            codigo=codigo,
            linea_base_id=materializada.linea_base_id,
            usuario_id=usuario_id,
        )
    return obra_id


def _congelar(
    contexto: ContextoPresupuesto,
    *,
    codigo: str,
    linea_base_id: uuid.UUID,
    usuario_id: uuid.UUID,
) -> None:
    """Congela la línea base recién sembrada; un rechazo del caso de uso sale como `SystemExit`.

    El caso de uso decide y escribe en su propia transacción: si se niega, no queda nada a medias y la
    obra conserva su `PLANEACION` con `BORRADOR`. La semilla no decide nada: solo traduce el rechazo.
    """
    try:
        congelar_linea_base(
            contexto,
            linea_base_id=linea_base_id,
            motivo=MOTIVO_CONGELADO,
            usuario_id=usuario_id,
        )
    except ErrorContrato as error:
        raise SystemExit(
            f"No se pudo congelar la obra {codigo}: {error.mensaje} Se queda en PLANEACION con su "
            "línea base BORRADOR; no se ha congelado nada."
        ) from None


def _usuario_por_correo(motor: Engine, correo: str) -> uuid.UUID:
    with motor.connect() as conexion:
        fila = conexion.execute(
            text("SELECT id FROM usuario WHERE email = :correo"), {"correo": correo}
        ).first()
    if fila is None:
        raise SystemExit(f"Falta el usuario {correo}; ejecuta herramientas.semilla_local.")
    return uuid.UUID(str(fila[0]))


def _argumentos(argv: Sequence[str]) -> argparse.Namespace:
    analizador = argparse.ArgumentParser(
        prog="python -m herramientas.semilla_linea_base_local",
        description="Siembra una obra de demostración con su línea base BORRADOR, solo en la base local.",
    )
    analizador.add_argument(
        "--congelar",
        action="store_true",
        help="congela la línea base sembrada: la obra queda ACTIVA con su línea base CONGELADA",
    )
    return analizador.parse_args(list(argv))


def main(argv: Sequence[str] = ()) -> int:
    """Punto de entrada: niega fuera de la base local, siembra y deja `OBRA_ID=` en la última línea."""
    congelar = _argumentos(argv).congelar
    try:
        exigir_base_local()
        codigo = os.environ.get(VARIABLE_CODIGO) or CODIGO_POR_OMISION
        correo = os.environ.get(VARIABLE_CORREO) or CORREO_POR_OMISION
        motor = crear_motor_aplicacion()
    except RuntimeError as error:
        raise SystemExit(str(error)) from None
    except ValueError:
        raise SystemExit(
            "Negado: CIMENTA_DB_PUERTO no es un numero entero. No se ha conectado."
        ) from None
    try:
        usuario_id = _usuario_por_correo(motor, correo)
        obra_id = sembrar_linea_base(
            motor,
            codigo=codigo,
            usuario_id=usuario_id,
            reloj=_reloj_del_sistema,
            congelar=congelar,
        )
    finally:
        motor.dispose()
    if congelar:
        print(f"Linea base CONGELADA en la obra {codigo}; la obra queda ACTIVA.")
    else:
        print(f"Linea base BORRADOR sembrada en la obra {codigo}.")
    print(f"OBRA_ID={obra_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
