"""Siembra en la base local de desarrollo un usuario por rol y 27 insumos sintéticos (TKT-010b, ADR-032).

Se invoca desde backend/ con:
uv run --env-file ../.env python -m herramientas.semilla_local

Es preparación de datos, no una prueba de permisos: se conecta con el rol de migración, como
`contrasenas_roles`. Solo escribe en la base local: rehúsa cualquier host que no sea 127.0.0.1,
localhost o ::1, y las variables `PGHOSTADDR` y `PGSERVICE`, que libpq usa en lugar del host de la
URL. La contraseña de siembra sale de su variable de entorno, nunca de un valor por omisión, y ningún
secreto ni hash se imprime.
"""

import os
import uuid
from datetime import date
from decimal import Decimal
from typing import Final, NamedTuple

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool

from cimenta.identidad.aplicacion.configuracion import ConfiguracionIdentidad
from cimenta.identidad.infraestructura.contrasenas import ContrasenasArgon2
from herramientas.conexion import leer_variable, url_migracion

HOSTS_LOCALES: Final = frozenset({"127.0.0.1", "localhost", "::1"})
VARIABLES_QUE_REDIRIGEN: Final = ("PGHOSTADDR", "PGSERVICE")
VARIABLE_CONTRASENA: Final = "CIMENTA_SEMILLA_CONTRASENA"
VIGENTE_DESDE: Final = date(2026, 1, 1)  # (asumido), A3


class UsuarioSemilla(NamedTuple):
    numero: int
    clave_rol: str
    correo: str
    nombre: str


class InsumoSemilla(NamedTuple):
    """Insumo sintético. `costo_unitario` es una cadena con cuatro decimales; se convierte con `Decimal`, nunca con `float`."""

    numero: int
    codigo: str
    descripcion: str
    unidad: str
    costo_unitario: str


class ResumenSiembra(NamedTuple):
    usuarios: int
    asignaciones: int
    insumos: int
    precios: int


USUARIOS: tuple[UsuarioSemilla, ...] = (
    UsuarioSemilla(
        1, "DIRECCION_GENERAL", "direccion_general@cimenta.test", "Dirección General · prueba local"
    ),
    UsuarioSemilla(
        2,
        "DIRECTOR_PROYECTOS",
        "director_proyectos@cimenta.test",
        "Director de Proyectos · prueba local",
    ),
    UsuarioSemilla(3, "RESIDENTE", "residente@cimenta.test", "Residente de obra · prueba local"),
    UsuarioSemilla(4, "COMPRAS", "compras@cimenta.test", "Compras · prueba local"),
    UsuarioSemilla(5, "ALMACEN", "almacen@cimenta.test", "Almacén · prueba local"),
    UsuarioSemilla(
        6, "ADMINISTRACION", "administracion@cimenta.test", "Administración · prueba local"
    ),
)

INSUMOS: tuple[InsumoSemilla, ...] = (
    InsumoSemilla(
        1, "TBR-001", "Panel de yeso regular de 12.7 mm, 1.22 x 2.44 m", "PZA", "168.5000"
    ),
    InsumoSemilla(
        2,
        "TBR-002",
        "Panel de yeso resistente a la humedad de 12.7 mm, 1.22 x 2.44 m",
        "PZA",
        "239.0000",
    ),
    InsumoSemilla(
        3,
        "TBR-003",
        "Panel de yeso resistente al fuego de 15.9 mm, 1.22 x 2.44 m",
        "PZA",
        "285.0000",
    ),
    InsumoSemilla(4, "TBR-004", "Panel de cemento de 12.7 mm, 1.22 x 2.44 m", "PZA", "452.0000"),
    InsumoSemilla(5, "TBR-005", "Poste metálico calibre 26 de 6.35 cm x 3.05 m", "PZA", "58.4000"),
    InsumoSemilla(6, "TBR-006", "Canal de amarre calibre 26 de 6.35 cm x 3.05 m", "PZA", "49.9000"),
    InsumoSemilla(7, "TBR-007", "Poste metálico calibre 20 de 9.20 cm x 3.05 m", "PZA", "96.7000"),
    InsumoSemilla(8, "TBR-008", "Canal listón calibre 26 x 3.05 m", "PZA", "38.5000"),
    InsumoSemilla(9, "TBR-009", "Canaleta de carga calibre 22 x 3.05 m", "PZA", "44.2000"),
    InsumoSemilla(10, "TBR-010", "Ángulo de amarre calibre 26 x 3.05 m", "PZA", "31.8000"),
    InsumoSemilla(11, "TBR-011", "Esquinero metálico de 3.05 m", "PZA", "27.6000"),
    InsumoSemilla(12, "TBR-012", "Alambre galvanizado calibre 12", "KG", "42.0000"),
    InsumoSemilla(
        13, "TBR-013", "Tornillo para panel de yeso de 1 pulgada, caja de 1000", "CAJA", "145.0000"
    ),
    InsumoSemilla(
        14,
        "TBR-014",
        "Tornillo de 7/16 pulgada con punta de broca, caja de 1000",
        "CAJA",
        "160.0000",
    ),
    InsumoSemilla(
        15,
        "TBR-015",
        "Taquete de expansión con clavo de 1/4 pulgada, caja de 100",
        "CAJA",
        "95.0000",
    ),
    InsumoSemilla(
        16, "TBR-016", "Compuesto en polvo para juntas, saco de 20 kg", "SACO", "245.0000"
    ),
    InsumoSemilla(17, "TBR-017", "Cinta de papel para juntas de 5 cm x 75 m", "ROLLO", "52.0000"),
    InsumoSemilla(
        18, "TBR-018", "Cinta de malla de fibra de vidrio de 5 cm x 90 m", "ROLLO", "68.0000"
    ),
    InsumoSemilla(
        19,
        "TBR-019",
        "Cinta de refuerzo para panel de cemento de 10 cm x 45 m",
        "ROLLO",
        "210.0000",
    ),
    InsumoSemilla(
        20,
        "TBR-020",
        "Mortero de acabado para panel de cemento, saco de 22.7 kg",
        "SACO",
        "289.0000",
    ),
    InsumoSemilla(21, "TBR-021", "Malla de fibra de vidrio para panel de cemento", "M2", "18.5000"),
    InsumoSemilla(
        22, "TBR-022", "Colchoneta aislante de fibra de vidrio de 7.6 cm", "M2", "64.0000"
    ),
    InsumoSemilla(23, "TBR-023", "Perfil de remate en J calibre 26 x 3.05 m", "PZA", "35.0000"),
    InsumoSemilla(
        24, "TBR-024", "Cinta de espuma para sellado acústico de 6 mm x 30 m", "ROLLO", "85.0000"
    ),
    InsumoSemilla(
        25, "TBR-025", "Plafón reticular de fibra mineral de 61 x 61 cm", "PZA", "41.5000"
    ),
    InsumoSemilla(
        26, "TBR-026", "Tee principal para suspensión de plafón de 3.66 m", "PZA", "52.3000"
    ),
    InsumoSemilla(
        27, "TBR-027", "Banda de refuerzo galvanizada calibre 20 de 15 cm", "ML", "47.0000"
    ),
)


def identificador(grupo: int, numero: int) -> uuid.UUID:
    """Identificador fijo de una fila sembrada: el mismo prefijo que la migración `v0008` (ADR-032)."""
    return uuid.UUID(f"c1e0a010-{grupo:04x}-4000-8000-{numero:012x}")


def exigir_base_local() -> None:
    """Niega la siembra antes de conectar si el destino no es la base local (CA-8, RNF-07).

    Primero comprueba que libpq no redirija la conexión con `PGHOSTADDR` o `PGSERVICE`; después, que
    el host de la URL sea local. Lanza `SystemExit` con un mensaje que nombra lo negado; si falta `CIMENTA_DB_HOST`, deja pasar el `RuntimeError` de `leer_variable`, que `main` traduce.
    """
    for variable in VARIABLES_QUE_REDIRIGEN:
        if os.environ.get(variable):
            raise SystemExit(
                f"Negado: {variable} esta definida y libpq la usa en lugar del host de la URL. "
                "Quitala del entorno para sembrar. No se ha conectado."
            )
    host = leer_variable("CIMENTA_DB_HOST")
    if host not in HOSTS_LOCALES:
        raise SystemExit(
            f"Negado: CIMENTA_DB_HOST apunta a '{host}', que no es exactamente uno de "
            "127.0.0.1, localhost o ::1. La siembra solo escribe en la base local. "
            "No se ha conectado."
        )


def sembrar(
    conexion: Connection, *, contrasena: str, contrasenas: ContrasenasArgon2
) -> ResumenSiembra:
    """Siembra usuarios, asignaciones de rol, insumos y precios generales dentro de la transacción de `conexion` (ADR-032).

    Cada sentencia se ejecuta con `executemany` y deja intacta cualquier fila que ya exista
    (`ON CONFLICT DO NOTHING`, `A6`). El hash de cada usuario sale de `contrasenas.derivar`, con su
    propia sal. El precio general de cada insumo solo se inserta si el insumo no tiene ya un precio
    general, sin restricción única (decisión de diseño de TKT-010). No se usa `rowcount`, que con
    `executemany` no es fiable.
    """
    sql_usuarios = """
        INSERT INTO usuario (id, nombre, email, password_hash, activo)
        VALUES (:id, :nombre, :email, :hash, true)
        ON CONFLICT DO NOTHING
    """
    sql_asignaciones = """
        INSERT INTO usuario_rol (id, usuario_id, rol_id)
        SELECT :id, u.id, r.id FROM usuario u JOIN rol r ON r.clave = :clave_rol
        WHERE u.id = :usuario_id
        ON CONFLICT DO NOTHING
    """
    sql_insumos = """
        INSERT INTO insumo (id, codigo, descripcion, tipo, unidad, activo, creado_en_importacion)
        VALUES (:id, :codigo, :descripcion, 'MATERIAL', :unidad, true, false)
        ON CONFLICT DO NOTHING
    """
    sql_precios = """
        INSERT INTO precio_insumo (id, insumo_id, obra_id, costo_unitario, vigente_desde, vigente_hasta)
        SELECT :id, i.id, NULL, :costo_unitario, :vigente_desde, NULL FROM insumo i
        WHERE i.id = :insumo_id
          AND NOT EXISTS (SELECT 1 FROM precio_insumo p WHERE p.insumo_id = i.id AND p.obra_id IS NULL)
        ON CONFLICT DO NOTHING
    """
    sql_resumen = """
        SELECT (SELECT count(*) FROM usuario WHERE id = ANY(:usuarios)),
               (SELECT count(*) FROM usuario_rol WHERE id = ANY(:asignaciones)),
               (SELECT count(*) FROM insumo WHERE id = ANY(:insumos)),
               (SELECT count(DISTINCT insumo_id) FROM precio_insumo WHERE insumo_id = ANY(:insumos) AND obra_id IS NULL)
    """

    filas_usuarios = [
        {
            "id": identificador(2, usuario.numero),
            "nombre": usuario.nombre,
            "email": usuario.correo,
            "hash": contrasenas.derivar(contrasena),
        }
        for usuario in USUARIOS
    ]
    conexion.execute(text(sql_usuarios), filas_usuarios)

    filas_asignaciones = [
        {
            "id": identificador(3, usuario.numero),
            "usuario_id": identificador(2, usuario.numero),
            "clave_rol": usuario.clave_rol,
        }
        for usuario in USUARIOS
    ]
    conexion.execute(text(sql_asignaciones), filas_asignaciones)

    filas_insumos = [
        {
            "id": identificador(4, insumo.numero),
            "codigo": insumo.codigo,
            "descripcion": insumo.descripcion,
            "unidad": insumo.unidad,
        }
        for insumo in INSUMOS
    ]
    conexion.execute(text(sql_insumos), filas_insumos)

    filas_precios = [
        {
            "id": identificador(5, insumo.numero),
            "insumo_id": identificador(4, insumo.numero),
            "costo_unitario": Decimal(insumo.costo_unitario),
            "vigente_desde": VIGENTE_DESDE,
        }
        for insumo in INSUMOS
    ]
    conexion.execute(text(sql_precios), filas_precios)

    usuarios_ids = [identificador(2, usuario.numero) for usuario in USUARIOS]
    asignaciones_ids = [identificador(3, usuario.numero) for usuario in USUARIOS]
    insumos_ids = [identificador(4, insumo.numero) for insumo in INSUMOS]
    fila = conexion.execute(
        text(sql_resumen),
        {"usuarios": usuarios_ids, "asignaciones": asignaciones_ids, "insumos": insumos_ids},
    ).one()
    return ResumenSiembra(
        usuarios=int(fila[0]),
        asignaciones=int(fila[1]),
        insumos=int(fila[2]),
        precios=int(fila[3]),
    )


def main() -> int:
    """Punto de entrada: niega la siembra fuera de la base local, siembra en una transacción y resume.

    Ningún secreto ni hash se imprime. Una sola transacción: si una sentencia falla, no queda nada escrito.
    """
    try:
        exigir_base_local()
        contrasena = leer_variable(VARIABLE_CONTRASENA)
        url = url_migracion()  # solo el int() del puerto puede lanzar ValueError aquí
    except RuntimeError as error:
        raise SystemExit(str(error)) from None
    except ValueError:
        raise SystemExit(
            "Negado: CIMENTA_DB_PUERTO no es un numero entero. No se ha conectado."
        ) from None
    contrasenas = ContrasenasArgon2(ConfiguracionIdentidad.desde_entorno(os.environ))
    # hide_parameters: sin ello, un fallo de sentencia vuelca los hashes en `[parameters: ...]`.
    motor = create_engine(url, poolclass=NullPool, hide_parameters=True)
    try:
        with motor.begin() as conexion:
            resumen = sembrar(conexion, contrasena=contrasena, contrasenas=contrasenas)
    except SQLAlchemyError as error:
        # El texto de PostgreSQL añade `DETAIL: Failing row contains (...)` con el hash: no se vuelca.
        original = getattr(error, "orig", None)
        sqlstate = getattr(original, "sqlstate", None)
        raise SystemExit(
            f"La siembra fallo ({type(original).__name__}, SQLSTATE {sqlstate}). "
            "No se ha escrito nada. El detalle se omite a proposito: puede contener un hash."
        ) from None
    finally:
        motor.dispose()
    print(
        f"Siembra local aplicada: {resumen.usuarios} usuarios, {resumen.asignaciones} asignaciones "
        f"de rol, {resumen.insumos} insumos y {resumen.precios} precios generales. "
        "La contrasena no se muestra."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
