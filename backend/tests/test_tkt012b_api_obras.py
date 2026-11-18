"""API del mantenimiento y del ciclo de vida de la obra, fila A7 de TKT-012b (TC-41 a TC-52).

Las cinco operaciones: `PATCH /api/v1/obras/{obra_id}`, `DELETE /api/v1/obras/{obra_id}` (`204` sin
cuerpo) y `POST /api/v1/obras/{obra_id}/suspension|reactivacion|cierre`. Cubre `CA-1` a `CA-6`, `CA-8` a
`CA-12` de la spec (`HDU-001` esc. 20; `RN-01`, `RN-25`, `PA-02`) contra PostgreSQL migrado con
`alembic upgrade head` y el rol de aplicación, por la aplicación real (`crear_aplicacion`) y un
`TestClient` HTTPS con sesión y CSRF. Las obras se siembran con SQL directo (`DatosPresupuesto`), no por
`POST`, y con la empresa de la migración `0008` (la única activa), para que un defecto del alta no pueda
tapar ni causar el fallo de la operación.

Cada rechazo comprueba el contrato de error completo con `exigir_error` (`tipo`, `codigo`, `mensaje`
literal, `errores` o `detalle`, `acciones`, la correlación de la cabecera y la validez contra el esquema
del borrador) y que no cambió nada: ni obras, ni líneas base, ni importaciones, ni bitácora. Los `403`
comprueban además el `DENEGAR` asentado, con el método y la ruta concretos.

Esta prueba no importa ningún módulo nuevo de producción: todo entra por HTTP y por `/openapi.json`, así
que el rojo de la fila no es de importación ni de entorno. Las cinco rutas no existen todavía: `PATCH` y
`DELETE` sobre `/api/v1/obras/{obra_id}` responden `405` (la ruta solo admite `GET`) y las tres `POST`
responden `404` `NO_ENCONTRADO` con la ruta como recurso.

Contrato que esta fila fija (el desarrollador lo implementa, no lo discute):

- `ObraCambios` (DTO del `PATCH`): `extra="forbid"`; `nombre`, `domicilio` (mismos tipos que `ObraNueva`),
  `retencion_destajo_pct`, `fondo_garantia_pct` (`PorcentajeEntrada`), `iva_acreditable` (`StrictBool`) y
  `umbral_alerta_pct` (`PorcentajeEntrada | None`), todos opcionales. Solo `umbral_alerta_pct` admite
  `null` y lo borra; `nombre`, `domicilio`, los dos porcentajes y `iva_acreditable` con `null` son `422`
  señalando el propio campo (`FORMATO`). Un campo desconocido o fijo (`codigo`, `tipo_contrato`,
  `estado`, `id`...) es `422` `VALOR_NO_PERMITIDO` señalando ese campo (`extra_forbidden`, comprobado con
  el manejador real en un experimento aparte). Un cuerpo `{}` es `422` `FORMATO` en `cuerpo`; `null` o sin
  cuerpo, `422` `OBLIGATORIO` en `cuerpo`; una lista, un texto o un JSON roto, `422` `FORMATO` en `cuerpo`.
- Las tres transiciones reciben `Motivo` (el de TKT-017 y TKT-029b): los mismos seis rechazos por motivo.
- `409` `CONFLICTO` `ESTADO_NO_PERMITE_OPERACION`: mensaje `La obra {codigo} está en {estado} y no admite
  esta operación.`; en el `PATCH`, detalle `{"estado"}` y sin acciones; en las transiciones, detalle
  `{"estado", "operaciones_admitidas"}` y una acción `POST` por operación admitida desde ese estado
  (`SUSPENDER_OBRA` a `/suspension`, `REACTIVAR_OBRA` a `/reactivacion`, `CERRAR_OBRA` a `/cierre`).
- `409` `CONFLICTO` `OBRA_CON_HISTORIAL`: mensaje `La obra {codigo} tiene historial y no se puede
  eliminar.`, detalle `{linea_base_congelada, lineas_base, importaciones, movimientos}` y las acciones
  `SUSPENDER_OBRA` y `CERRAR_OBRA` que el estado admite. Con una fila de otro módulo que cuelga de la obra
  (`23001`), el mismo detalle de cuatro claves con `movimientos` 1: el nombre de la restricción no sale
  al cliente (CWE-209, ciclo de corrección 2).
- `404` `NO_ENCONTRADO` con `recurso` `obra`; `obra_id` que no es UUID, `422` en `obra_id`.

Rojo esperado de la fila: ninguna prueba de comportamiento de las cinco rutas puede nacer en verde. El
`409` de `CONCURRENCIA` y las carreras no son de esta fila (A9).

Mutantes que esta fila pone en rojo: una ruta sin `verificar_origen`, con `exigir_rol` antes que él, con
otros roles o `async def`; un código de estado distinto de `200`, `204`, `409`, `404` o `422`; quitar el
`extra="forbid"` de `ObraCambios`, un patrón o un tope de sus campos, o el `StrictBool`; admitir `null` en
`nombre`; ofrecer en el `409` una acción que el estado no admite; no asentar el cambio; cruzar dos
columnas de porcentaje; un `UPDATE` sin `WHERE`.
"""

# Las fixtures importadas por nombre (`abrir_sesion`, `base`) se piden como parámetro: Ruff lo lee como
# F811. `pyproject.toml` lo exime solo para `tests/test_tkt017_api_*.py`; aquí se exime en el archivo.
# ruff: noqa: F811

from __future__ import annotations

import inspect
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import pytest
from fastapi.testclient import TestClient

from cimenta.identidad.api.dependencias import sesion_vigente, verificar_origen
from herramientas.soporte_tkt017_api import (
    SIN_PAR_VALIDO,
    TOKEN_CSRF,
    Sesion,
    abrir_sesion,  # noqa: F401
    base,  # noqa: F401
    borrador_comparable,
    cabeceras_de,
    construir_aplicacion,
    exigir_denegacion,
    exigir_error,
    llamadas,
    parametros_de,
    resolver,
    rutas_de,
    validar_contra,
)
from herramientas.soporte_tkt017_api import publicado as contrato_publicado
from herramientas.soporte_tkt017_entorno import Base

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta.
    from conftest import DatosPresupuesto, RelojDePrueba

RUTA = "/api/v1/obras"
TIPO_CONTRATO = "PRECIO_ALZADO_MAXIMO_GARANTIZADO"
CODIGO = "AP-058-25"
NOMBRE_INICIAL = f"Obra {CODIGO}"
DOMICILIO_INICIAL = "Calle de prueba 1"
ROLES_QUE_OPERAN = ["DIRECTOR_PROYECTOS", "DIRECCION_GENERAL"]
ROLES_SIN_ESCRITURA = ["RESIDENTE", "COMPRAS", "ALMACEN", "ADMINISTRACION"]
MOTIVO = "Decisión de la dirección por falta de anticipo"
CLAVES_DE_OBRA = {
    "id",
    "codigo",
    "nombre",
    "domicilio",
    "tipo_contrato",
    "retencion_destajo_pct",
    "fondo_garantia_pct",
    "iva_acreditable",
    "umbral_alerta_pct",
    "estado",
    "linea_base_vigente_id",
    "creado_en",
}

MENSAJE_ROL_INSUFICIENTE = "Tu rol no permite esta operación."
MENSAJE_ORIGEN_NO_VERIFICADO = (
    "No se pudo comprobar que la petición venga de CIMENTA. Recarga la página e inténtalo de nuevo."
)
MENSAJE_SIN_SESION = "No hay una sesión iniciada."
MENSAJE_OBRA_NO_EXISTE = "La obra no existe."
MENSAJE_ESTADO = "La obra {codigo} está en {estado} y no admite esta operación."
MENSAJE_CON_HISTORIAL = "La obra {codigo} tiene historial y no se puede eliminar."
MENSAJE_PORCENTAJE_FUERA_DE_RANGO = "El porcentaje debe estar entre 0 y 1 (0 % a 100 %)."
MENSAJE_UMBRAL_NEGATIVO = "El umbral de alerta no puede ser negativo."
MENSAJES_DE_VALIDACION = {
    "OBLIGATORIO": "El campo es obligatorio.",
    "FORMATO": "El valor no tiene el formato esperado.",
    "DEMASIADO_LARGO": "El valor excede la longitud máxima.",
    "VALOR_NO_PERMITIDO": "El valor no está entre los permitidos.",
    "FUERA_DE_RANGO": "El valor está fuera del rango permitido.",
}

# Operaciones que admite cada estado, en el orden de `OperacionObra`, y la acción de cada una (D-2).
ADMITIDAS_POR_ESTADO: dict[str, tuple[str, ...]] = {
    "PLANEACION": ("CERRAR",),
    "ACTIVA": ("SUSPENDER", "CERRAR"),
    "SUSPENDIDA": ("REACTIVAR", "CERRAR"),
    "CERRADA": (),
}
ACCION_DE_OPERACION = {
    "SUSPENDER": ("SUSPENDER_OBRA", "suspension"),
    "REACTIVAR": ("REACTIVAR_OBRA", "reactivacion"),
    "CERRAR": ("CERRAR_OBRA", "cierre"),
}
# Las acciones del `409` `OBRA_CON_HISTORIAL` son solo las dos que el borrador declara.
ACCIONES_CON_HISTORIAL_POR_ESTADO: dict[str, tuple[str, ...]] = {
    "PLANEACION": ("CERRAR",),
    "ACTIVA": ("SUSPENDER", "CERRAR"),
    "SUSPENDIDA": ("CERRAR",),
    "CERRADA": (),
}

SIN_CUERPO = object()  # la petición no lleva cuerpo


@dataclass(frozen=True)
class Operacion:
    """Una de las cinco operaciones, con un cuerpo válido y el estado en el que procede."""

    nombre: str
    metodo: str
    sufijo: str
    cuerpo: object
    estado: str


OPERACIONES = [
    Operacion("patch", "PATCH", "", {"nombre": "Nombre corregido de la obra"}, "ACTIVA"),
    Operacion("delete", "DELETE", "", SIN_CUERPO, "PLANEACION"),
    Operacion("suspension", "POST", "/suspension", {"motivo": MOTIVO}, "ACTIVA"),
    Operacion("reactivacion", "POST", "/reactivacion", {"motivo": MOTIVO}, "SUSPENDIDA"),
    Operacion("cierre", "POST", "/cierre", {"motivo": MOTIVO}, "ACTIVA"),
]
OPERACIONES_POST = [operacion for operacion in OPERACIONES if operacion.metodo == "POST"]


def _ruta(obra_id: object, sufijo: str = "") -> str:
    return f"{RUTA}/{obra_id}{sufijo}"


# --------------------------------------------------------------------------- ayudas de la prueba


def _llamar(
    cliente: TestClient,
    metodo: str,
    ruta: str,
    sesion: Sesion | None,
    cuerpo: object = SIN_CUERPO,
    *,
    cookie_csrf: str | None = TOKEN_CSRF,
    cabecera_csrf: str | None = TOKEN_CSRF,
) -> Any:
    """Una petición con la cookie de sesión y el par CSRF indicado (por omisión, uno válido).

    `cuerpo` es JSON; si es `bytes` viaja tal cual (con `Content-Type: application/json`), para probar
    `null`, el cuerpo vacío o un JSON roto, y `SIN_CUERPO` no manda cuerpo.
    """
    cabeceras = cabeceras_de(
        None if sesion is None else sesion.sesion_id, cookie_csrf, cabecera_csrf
    )
    if cuerpo is SIN_CUERPO:
        return cliente.request(metodo, ruta, headers=cabeceras)
    if isinstance(cuerpo, bytes):
        return cliente.request(
            metodo, ruta, content=cuerpo, headers={**cabeceras, "Content-Type": "application/json"}
        )
    return cliente.request(metodo, ruta, json=cuerpo, headers=cabeceras)


def _pedir(
    cliente: TestClient,
    operacion: Operacion,
    obra_id: object,
    sesion: Sesion | None,
    **par: Any,
) -> Any:
    """La operación con su cuerpo válido sobre `obra_id`."""
    return _llamar(
        cliente,
        operacion.metodo,
        _ruta(obra_id, operacion.sufijo),
        sesion,
        operacion.cuerpo,
        **par,
    )


def _patch(cliente: TestClient, sesion: Sesion | None, obra_id: object, cuerpo: object) -> Any:
    return _llamar(cliente, "PATCH", _ruta(obra_id), sesion, cuerpo)


def _borrar(cliente: TestClient, sesion: Sesion | None, obra_id: object) -> Any:
    return _llamar(cliente, "DELETE", _ruta(obra_id), sesion)


def _transicion(
    cliente: TestClient, sesion: Sesion | None, obra_id: object, sufijo: str, cuerpo: object
) -> Any:
    return _llamar(cliente, "POST", _ruta(obra_id, sufijo), sesion, cuerpo)


def _leer(cliente: TestClient, sesion: Sesion | None, ruta: str) -> Any:
    return cliente.get(ruta, headers=cabeceras_de(None if sesion is None else sesion.sesion_id))


def _cuenta(base: Base, consulta: Any, *parametros: object) -> int:
    fila = base.conexion.execute(consulta, parametros).fetchone()
    assert fila is not None
    return int(fila[0])


def _foto(base: Base) -> dict[str, object]:
    """Lo que un rechazo no debe cambiar: obras, historial propio y bitácora (sin los `DENEGAR`)."""
    return {
        "obras": base.filas("SELECT * FROM obra ORDER BY id"),
        "lineas_base": base.filas("SELECT * FROM linea_base ORDER BY id"),
        "importaciones": base.filas("SELECT id, obra_id, estado FROM importacion ORDER BY id"),
        "requisiciones": base.filas("SELECT id, obra_id, estado FROM requisicion ORDER BY id"),
        "asientos": base.filas(
            "SELECT id, accion::text, entidad_id FROM bitacora WHERE accion <> 'DENEGAR' ORDER BY id"
        ),
    }


def _asientos(base: Base, entidad_id: uuid.UUID) -> list[tuple[Any, ...]]:
    """Los asientos de una entidad con lo que el contrato de bitácora promete, en orden de ocurrencia."""
    return base.filas(
        "SELECT accion::text, entidad_tipo, entidad_id, usuario_id, ocurrido_en, motivo, obra_id, "
        "datos_antes, datos_despues FROM bitacora WHERE entidad_id = %s ORDER BY ocurrido_en, id",
        entidad_id,
    )


def _fila_de_obra(base: Base, obra_id: uuid.UUID) -> list[tuple[Any, ...]]:
    return base.filas("SELECT * FROM obra WHERE id = %s", obra_id)


def _sin_fechas(obra: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in obra.items() if k not in {"creado_en", "actualizado_en"}}


def _obra_esperada(
    obra_id: uuid.UUID | str, *, codigo: str = CODIGO, estado: str = "ACTIVA", **cambios: object
) -> dict[str, Any]:
    """La `Obra` sembrada por `fabricar_obra` (sin línea base) tal como la devuelve el API, sin fechas."""
    obra: dict[str, Any] = {
        "id": str(obra_id),
        "codigo": codigo,
        "nombre": f"Obra {codigo}",
        "domicilio": DOMICILIO_INICIAL,
        "tipo_contrato": TIPO_CONTRATO,
        "retencion_destajo_pct": "0.150000",
        "fondo_garantia_pct": "0.050000",
        "iva_acreditable": True,
        "umbral_alerta_pct": "0.100000",
        "estado": estado,
        "linea_base_vigente_id": None,
    }
    return {**obra, **cambios}


def _errores_de_validacion(
    respuesta: Any, errores: list[tuple[str, str] | tuple[str, str, str]]
) -> dict[str, Any]:
    """El `422` `VALIDACION` completo con uno o varios `(campo, codigo[, mensaje])`."""
    cantidad = len(errores)
    return exigir_error(
        respuesta,
        estado=422,
        esperado={
            "tipo": "VALIDACION",
            "mensaje": (
                "La petición tiene 1 campo inválido."
                if cantidad == 1
                else f"La petición tiene {cantidad} campos inválidos."
            ),
            "errores": [
                {
                    "campo": error[0],
                    "codigo": error[1],
                    "mensaje": error[2] if len(error) == 3 else MENSAJES_DE_VALIDACION[error[1]],
                }
                for error in errores
            ],
        },
        esquema="ErrorValidacion",
    )


def _error_de_validacion(
    respuesta: Any, campo: str, codigo: str, mensaje: str | None = None
) -> dict[str, Any]:
    error = (campo, codigo) if mensaje is None else (campo, codigo, mensaje)
    return _errores_de_validacion(respuesta, [error])


def _acciones_esperadas(obra_id: uuid.UUID, operaciones: tuple[str, ...]) -> list[dict[str, str]]:
    return [
        {
            "clave": ACCION_DE_OPERACION[operacion][0],
            "metodo": "POST",
            "ruta": _ruta(obra_id, f"/{ACCION_DE_OPERACION[operacion][1]}"),
        }
        for operacion in operaciones
    ]


def _exigir_estado_no_permite(
    respuesta: Any, obra_id: uuid.UUID, *, estado: str, con_operaciones: bool
) -> None:
    """El `409` `CONFLICTO` `ESTADO_NO_PERMITE_OPERACION` completo: nunca `REGLA_NEGOCIO`.

    En el `PATCH` el detalle trae solo el estado y no hay acciones (una obra cerrada no admite nada). En las
    transiciones el detalle suma las operaciones admitidas y cada una viene como acción `POST` de esa obra.
    """
    admitidas = ADMITIDAS_POR_ESTADO[estado]
    cuerpo = exigir_error(
        respuesta,
        estado=409,
        esperado={
            "tipo": "CONFLICTO",
            "codigo": "ESTADO_NO_PERMITE_OPERACION",
            "mensaje": MENSAJE_ESTADO.format(codigo=CODIGO, estado=estado),
            "detalle": (
                {"estado": estado, "operaciones_admitidas": list(admitidas)}
                if con_operaciones
                else {"estado": estado}
            ),
            "acciones": _acciones_esperadas(obra_id, admitidas) if con_operaciones else [],
        },
        esquema="ErrorConflictoEstado",
    )
    assert "regla" not in cuerpo


def _exigir_con_historial(
    respuesta: Any,
    obra_id: uuid.UUID,
    *,
    estado: str,
    detalle: dict[str, object],
) -> None:
    """El `409` `CONFLICTO` `OBRA_CON_HISTORIAL` completo, con las acciones que el estado admite."""
    cuerpo = exigir_error(
        respuesta,
        estado=409,
        esperado={
            "tipo": "CONFLICTO",
            "codigo": "OBRA_CON_HISTORIAL",
            "mensaje": MENSAJE_CON_HISTORIAL.format(codigo=CODIGO),
            "detalle": detalle,
            "acciones": _acciones_esperadas(obra_id, ACCIONES_CON_HISTORIAL_POR_ESTADO[estado]),
        },
        esquema="ErrorConflictoEstado",
    )
    assert "regla" not in cuerpo


def _detalle_de_historial(
    *, congelada: bool = False, lineas_base: int = 0, importaciones: int = 0, movimientos: int = 0
) -> dict[str, object]:
    return {
        "linea_base_congelada": congelada,
        "lineas_base": lineas_base,
        "importaciones": importaciones,
        "movimientos": movimientos,
    }


# La historia que cuelga de una obra, y el detalle que el `409` debe contar.
HISTORIAS: dict[str, dict[str, object]] = {
    "congelada": _detalle_de_historial(congelada=True, lineas_base=1),
    "borrador": _detalle_de_historial(lineas_base=1),
    "importaciones": _detalle_de_historial(importaciones=2),
}


def _dar_historia(datos: DatosPresupuesto, obra_id: uuid.UUID, historia: str) -> None:
    if historia == "congelada":
        datos.linea_base(estado="CONGELADA", obra_id=obra_id)
    elif historia == "borrador":
        datos.linea_base(estado="BORRADOR", obra_id=obra_id)
    else:
        assert historia == "importaciones"
        datos.importacion(obra_id=obra_id)
        datos.importacion(obra_id=obra_id)


@pytest.fixture
def empresa_de_la_migracion(base: Base) -> uuid.UUID:
    """La única empresa activa de la base migrada (`0008`): la que toma el alta."""
    filas = base.filas("SELECT id FROM empresa WHERE activa")
    assert len(filas) == 1, f"La migración debe dejar una empresa activa y deja {len(filas)}"
    return uuid.UUID(str(filas[0][0]))


@pytest.fixture
def fabricar_obra(
    datos_presupuesto: DatosPresupuesto, empresa_de_la_migracion: uuid.UUID
) -> Callable[..., uuid.UUID]:
    """Una obra con tres porcentajes distintos (un cruce de columnas se nota) y el estado pedido."""
    creador = datos_presupuesto.usuario()

    def fabricar(
        *,
        codigo: str = CODIGO,
        estado: str = "ACTIVA",
        umbral: Decimal | None = Decimal("0.100000"),
    ) -> uuid.UUID:
        return datos_presupuesto.obra(
            codigo=codigo,
            empresa_id=empresa_de_la_migracion,
            creado_por_id=creador,
            estado=estado,
            retencion_destajo_pct=Decimal("0.150000"),
            fondo_garantia_pct=Decimal("0.050000"),
            umbral_alerta_pct=umbral,
            iva_acreditable=True,
        )

    return fabricar


# --------------------------------------------------------------------------- TC-41 · CA-1


@pytest.mark.parametrize("rol", ROLES_QUE_OPERAN)
def test_tkt012b_ca1_api_patch_corrige_nombre_y_porcentaje_responde_200(
    rol: str,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    fabricar_obra: Callable[..., uuid.UUID],
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """TC-41 · CA-1 · RN-25 · PA-02 — `200` con la `Obra` del borrador y los porcentajes como cadena de seis decimales.

    Para Director de Proyectos y para Dirección General: cambian `nombre` y `retencion_destajo_pct`
    (`"0.10"` vuelve como `"0.100000"`); el código, el tipo de contrato, el estado y los campos que no
    viajan (el fondo y el umbral) no cambian. La fila queda sellada con quién y cuándo, y la bitácora tiene
    un `ACTUALIZAR` de esa obra con el valor anterior y el nuevo **solo** de los campos cambiados. Otra
    obra no se toca (un `UPDATE` sin `WHERE` lo delataría).
    """
    usuario = abrir_sesion((rol,))
    obra_id = fabricar_obra()
    otra = fabricar_obra(codigo="AP-777-26")
    otra_antes = _fila_de_obra(base, otra)

    respuesta = _patch(
        cliente,
        usuario,
        obra_id,
        {"nombre": "Union Square F2 (ampliación)", "retencion_destajo_pct": "0.10"},
    )

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.headers["content-type"].startswith("application/json")
    cuerpo = respuesta.json()
    validar_contra("Obra", cuerpo)
    assert set(cuerpo) == CLAVES_DE_OBRA | {"actualizado_en"}
    assert datetime.fromisoformat(cuerpo["actualizado_en"]) == reloj_de_prueba.ahora
    assert _sin_fechas(cuerpo) == _obra_esperada(
        obra_id, nombre="Union Square F2 (ampliación)", retencion_destajo_pct="0.100000"
    )
    assert base.filas(
        "SELECT codigo, tipo_contrato, estado, nombre, domicilio, retencion_destajo_pct, "
        "fondo_garantia_pct, iva_acreditable, umbral_alerta_pct, actualizado_en, actualizado_por_id "
        "FROM obra WHERE id = %s",
        obra_id,
    ) == [
        (
            CODIGO,
            TIPO_CONTRATO,
            "ACTIVA",
            "Union Square F2 (ampliación)",
            DOMICILIO_INICIAL,
            "0.100000",
            "0.050000",
            True,
            "0.100000",
            reloj_de_prueba.ahora,
            usuario.usuario_id,
        )
    ]
    assert _asientos(base, obra_id) == [
        (
            "ACTUALIZAR",
            "obra",
            obra_id,
            usuario.usuario_id,
            reloj_de_prueba.ahora,
            None,
            obra_id,
            {"nombre": NOMBRE_INICIAL, "retencion_destajo_pct": "0.150000"},
            {"nombre": "Union Square F2 (ampliación)", "retencion_destajo_pct": "0.100000"},
        )
    ]
    assert _fila_de_obra(base, otra) == otra_antes
    assert _asientos(base, otra) == []


def test_tkt012b_ca1_api_patch_cambia_los_seis_campos_sin_cruzar_columnas(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    fabricar_obra: Callable[..., uuid.UUID],
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """TC-41 · CA-1 — los seis campos editables cambian a la vez y cada valor cae en su columna.

    Retención, fondo y umbral parten de tres valores distintos y llegan a otros tres: un intercambio
    entre columnas, o un campo que no se escribe, se nota. El nombre se guarda sin espacios en los
    extremos. El asiento trae el antes y el después de los seis, con los porcentajes en escala 6.
    """
    usuario = abrir_sesion()
    obra_id = fabricar_obra()

    respuesta = _patch(
        cliente,
        usuario,
        obra_id,
        {
            "nombre": "  Obra renombrada  ",
            "domicilio": "Av. Nueva 99",
            "retencion_destajo_pct": "0.20",
            "fondo_garantia_pct": "0.07",
            "iva_acreditable": False,
            "umbral_alerta_pct": "0.3",
        },
    )

    assert respuesta.status_code == 200, respuesta.text
    validar_contra("Obra", respuesta.json())
    assert _sin_fechas(respuesta.json()) == _obra_esperada(
        obra_id,
        nombre="Obra renombrada",
        domicilio="Av. Nueva 99",
        retencion_destajo_pct="0.200000",
        fondo_garantia_pct="0.070000",
        iva_acreditable=False,
        umbral_alerta_pct="0.300000",
    )
    assert base.filas(
        "SELECT nombre, domicilio, retencion_destajo_pct, fondo_garantia_pct, iva_acreditable, "
        "umbral_alerta_pct FROM obra WHERE id = %s",
        obra_id,
    ) == [("Obra renombrada", "Av. Nueva 99", "0.200000", "0.070000", False, "0.300000")]
    asientos = _asientos(base, obra_id)
    assert [fila[0] for fila in asientos] == ["ACTUALIZAR"]
    assert asientos[0][7] == {
        "nombre": NOMBRE_INICIAL,
        "domicilio": DOMICILIO_INICIAL,
        "retencion_destajo_pct": "0.150000",
        "fondo_garantia_pct": "0.050000",
        "iva_acreditable": True,
        "umbral_alerta_pct": "0.100000",
    }
    assert asientos[0][8] == {
        "nombre": "Obra renombrada",
        "domicilio": "Av. Nueva 99",
        "retencion_destajo_pct": "0.200000",
        "fondo_garantia_pct": "0.070000",
        "iva_acreditable": False,
        "umbral_alerta_pct": "0.300000",
    }


@pytest.mark.parametrize("estado", ["PLANEACION", "ACTIVA", "SUSPENDIDA"])
def test_tkt012b_ca1_api_patch_se_edita_en_todo_estado_menos_cerrada(
    estado: str,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    fabricar_obra: Callable[..., uuid.UUID],
) -> None:
    """TC-22 · CA-1 · D-3 — una obra en `PLANEACION`, `ACTIVA` o `SUSPENDIDA` se edita y conserva su estado.

    Solo `CERRADA` bloquea la edición (`CA-4`): una obra suspendida se corrige sin reactivarla.
    """
    usuario = abrir_sesion()
    obra_id = fabricar_obra(estado=estado)

    respuesta = _patch(cliente, usuario, obra_id, {"nombre": "Nombre corregido"})

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["estado"] == estado
    assert respuesta.json()["nombre"] == "Nombre corregido"
    assert base.filas("SELECT estado, nombre FROM obra WHERE id = %s", obra_id) == [
        (estado, "Nombre corregido")
    ]
    assert [fila[0] for fila in _asientos(base, obra_id)] == ["ACTUALIZAR"]


def test_tkt012b_ca1_api_patch_umbral_null_borra_el_umbral(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    fabricar_obra: Callable[..., uuid.UUID],
) -> None:
    """TC-45 · CA-1 · PA-18 — `umbral_alerta_pct: null` borra el umbral (`200`, `null` en la respuesta y en la base).

    Es el único campo que admite `null`. El asiento guarda el valor que tenía y `null` como el nuevo.
    """
    usuario = abrir_sesion()
    obra_id = fabricar_obra()

    respuesta = _patch(cliente, usuario, obra_id, {"umbral_alerta_pct": None})

    assert respuesta.status_code == 200, respuesta.text
    validar_contra("Obra", respuesta.json())
    assert respuesta.json()["umbral_alerta_pct"] is None
    assert _sin_fechas(respuesta.json()) == _obra_esperada(obra_id, umbral_alerta_pct=None)
    assert base.filas("SELECT umbral_alerta_pct FROM obra WHERE id = %s", obra_id) == [(None,)]
    asientos = _asientos(base, obra_id)
    assert [fila[0] for fila in asientos] == ["ACTUALIZAR"]
    assert asientos[0][7] == {"umbral_alerta_pct": "0.100000"}
    assert asientos[0][8] == {"umbral_alerta_pct": None}


def test_tkt012b_ca1_api_patch_sin_cambios_reales_responde_200_sin_asiento(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    fabricar_obra: Callable[..., uuid.UUID],
) -> None:
    """TC-24 · CA-1 (variante) — un cuerpo que no cambia ningún valor responde `200` con la obra tal cual y no asienta.

    Los valores iguales en distinta escritura (`"0.15"` por `"0.150000"`) tampoco cuentan como cambio.
    La fila no se sella: ni `actualizado_en` ni `actualizado_por_id`.
    """
    usuario = abrir_sesion()
    obra_id = fabricar_obra()
    antes = _foto(base)

    respuesta = _patch(
        cliente,
        usuario,
        obra_id,
        {
            "nombre": NOMBRE_INICIAL,
            "retencion_destajo_pct": "0.15",
            "umbral_alerta_pct": "0.1",
            "iva_acreditable": True,
        },
    )

    assert respuesta.status_code == 200, respuesta.text
    validar_contra("Obra", respuesta.json())
    assert _sin_fechas(respuesta.json()) == _obra_esperada(obra_id)
    assert _foto(base) == antes
    assert base.filas(
        "SELECT actualizado_en, actualizado_por_id FROM obra WHERE id = %s", obra_id
    ) == [(None, None)]
    assert _asientos(base, obra_id) == []


@pytest.mark.parametrize(
    "cuerpo",
    [
        pytest.param({"nombre": "n" * 200}, id="nombre_de_200"),
        pytest.param({"domicilio": "d" * 500}, id="domicilio_de_500"),
        pytest.param({"retencion_destajo_pct": "0.000000"}, id="retencion_cero"),
        pytest.param({"retencion_destajo_pct": "1.000000"}, id="retencion_uno"),
        pytest.param({"fondo_garantia_pct": "0.000000"}, id="fondo_cero"),
        pytest.param({"fondo_garantia_pct": "1.000000"}, id="fondo_uno"),
        pytest.param({"umbral_alerta_pct": "0.000000"}, id="umbral_cero"),
        pytest.param({"umbral_alerta_pct": "2.500000"}, id="umbral_sin_techo"),
    ],
)
def test_tkt012b_ca3_api_patch_los_bordes_de_longitud_y_de_rango_se_admiten(
    cuerpo: dict[str, str],
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    fabricar_obra: Callable[..., uuid.UUID],
) -> None:
    """TC-44 · CA-3 · PA-02 · PA-18 — los topes mismos (200 y 500) y los bordes `0` y `1` de los porcentajes dan `200`.

    El umbral no tiene techo (no negativo): `2.500000` también. El valor guardado es el enviado. Un
    rechazo por `>=` en lugar de `>` se nota aquí y no en los casos de rechazo.
    """
    usuario = abrir_sesion()
    obra_id = fabricar_obra()

    respuesta = _patch(cliente, usuario, obra_id, cuerpo)

    assert respuesta.status_code == 200, respuesta.text
    validar_contra("Obra", respuesta.json())
    guardado = dict(
        zip(
            (
                "nombre",
                "domicilio",
                "retencion_destajo_pct",
                "fondo_garantia_pct",
                "umbral_alerta_pct",
            ),
            base.filas(
                "SELECT nombre, domicilio, retencion_destajo_pct, fondo_garantia_pct, "
                "umbral_alerta_pct FROM obra WHERE id = %s",
                obra_id,
            )[0],
            strict=True,
        )
    )
    for campo, valor in cuerpo.items():
        assert respuesta.json()[campo] == valor
        assert guardado[campo] == valor


# --------------------------------------------------------------------------- TC-42 · CA-2


CAMPOS_QUE_NO_SE_EDITAN = [
    pytest.param({"codigo": "AP-999-99"}, ["codigo"], id="codigo"),
    pytest.param({"tipo_contrato": TIPO_CONTRATO}, ["tipo_contrato"], id="tipo_contrato_igual"),
    pytest.param({"tipo_contrato": "OTRO"}, ["tipo_contrato"], id="tipo_contrato_otro"),
    pytest.param({"estado": "CERRADA"}, ["estado"], id="estado"),
    pytest.param({"estado": "ACTIVA"}, ["estado"], id="estado_igual_al_actual"),
    pytest.param(
        {"nombre": "Otro nombre", "codigo": "AP-999-99"},
        ["codigo"],
        id="codigo_junto_a_un_cambio_valido",
    ),
    pytest.param({"codigo": "AP-999-99", "estado": "CERRADA"}, ["codigo", "estado"], id="dos"),
    pytest.param(
        {"codigo": "AP-999-99", "tipo_contrato": TIPO_CONTRATO, "estado": "CERRADA"},
        ["codigo", "tipo_contrato", "estado"],
        id="los_tres",
    ),
    pytest.param({"id": str(uuid.uuid4())}, ["id"], id="id"),
    pytest.param({"empresa_id": str(uuid.uuid4())}, ["empresa_id"], id="empresa_id"),
    pytest.param(
        {"linea_base_vigente_id": str(uuid.uuid4())},
        ["linea_base_vigente_id"],
        id="linea_base_vigente_id",
    ),
    pytest.param({"campo_inventado": 1}, ["campo_inventado"], id="campo_inventado"),
]


@pytest.mark.parametrize(("cuerpo", "campos"), CAMPOS_QUE_NO_SE_EDITAN)
def test_tkt012b_ca2_api_patch_rechaza_los_campos_que_no_se_editan_o_desconocidos(
    cuerpo: dict[str, object],
    campos: list[str],
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    fabricar_obra: Callable[..., uuid.UUID],
) -> None:
    """TC-42 · CA-2 — `codigo`, `tipo_contrato`, `estado` y todo campo desconocido: `422` `VALIDACION` `VALOR_NO_PERMITIDO` en ese campo.

    `ObraCambios` rechaza lo que no declara (`extra_forbidden`, comprobado con el manejador real: el
    campo es el nombre enviado y el código, `VALOR_NO_PERMITIDO`). Aunque el mismo cuerpo traiga un
    cambio válido, no se escribe nada: ni la obra ni la bitácora cambian. Con varios campos fijos hay un
    error por cada uno, en el orden del cuerpo.
    """
    usuario = abrir_sesion()
    obra_id = fabricar_obra()
    antes = _foto(base)

    respuesta = _patch(cliente, usuario, obra_id, cuerpo)

    _errores_de_validacion(respuesta, [(campo, "VALOR_NO_PERMITIDO") for campo in campos])
    assert _foto(base) == antes


# --------------------------------------------------------------------------- TC-43 · CA-2


CUERPOS_QUE_NO_SON_CAMBIOS = [
    pytest.param({}, "FORMATO", id="objeto_vacio"),
    pytest.param(b"null", "FORMATO", id="null"),
    pytest.param(b"", "OBLIGATORIO", id="sin_cuerpo"),
    pytest.param([], "FORMATO", id="lista"),
    pytest.param(["nombre"], "FORMATO", id="lista_con_elementos"),
    pytest.param("texto", "FORMATO", id="texto"),
    pytest.param(7, "FORMATO", id="numero"),
    pytest.param(b"{no es json", "FORMATO", id="json_roto"),
]


@pytest.mark.parametrize(("cuerpo", "codigo"), CUERPOS_QUE_NO_SON_CAMBIOS)
def test_tkt012b_ca2_api_patch_cuerpo_vacio_nulo_o_que_no_es_objeto_responde_422(
    cuerpo: object,
    codigo: str,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    fabricar_obra: Callable[..., uuid.UUID],
) -> None:
    """TC-43 · CA-2 — `{}`, `null`, sin cuerpo, una lista, un texto, un número o un JSON roto: `422` `VALIDACION` en `cuerpo`.

    `{}` y lo que no es un objeto (incluido el literal `null`) son `FORMATO`; el cuerpo vacío, `OBLIGATORIO`
    (FastAPI lo trata como cuerpo ausente). Un `PATCH` sin nada que cambiar no es un `200` mudo. La obra y la
    bitácora quedan como estaban.
    """
    usuario = abrir_sesion()
    obra_id = fabricar_obra()
    antes = _foto(base)

    respuesta = _patch(cliente, usuario, obra_id, cuerpo)

    _error_de_validacion(respuesta, "cuerpo", codigo)
    assert _foto(base) == antes


# --------------------------------------------------------------------------- TC-44 · CA-3


CASOS_DE_FORMA = [
    pytest.param({"nombre": ""}, "nombre", "OBLIGATORIO", id="nombre_vacio"),
    pytest.param({"nombre": "   "}, "nombre", "OBLIGATORIO", id="nombre_en_blanco"),
    pytest.param({"nombre": "Obra\u0000"}, "nombre", "FORMATO", id="nul_en_nombre"),
    pytest.param({"nombre": "n" * 201}, "nombre", "DEMASIADO_LARGO", id="nombre_de_201"),
    pytest.param({"nombre": None}, "nombre", "FORMATO", id="nombre_null"),
    pytest.param({"nombre": 123}, "nombre", "FORMATO", id="nombre_numero"),
    pytest.param({"domicilio": ""}, "domicilio", "OBLIGATORIO", id="domicilio_vacio"),
    pytest.param({"domicilio": "   "}, "domicilio", "OBLIGATORIO", id="domicilio_en_blanco"),
    pytest.param({"domicilio": "\u0000Calle"}, "domicilio", "FORMATO", id="nul_en_domicilio"),
    pytest.param({"domicilio": "d" * 501}, "domicilio", "DEMASIADO_LARGO", id="domicilio_de_501"),
    pytest.param({"domicilio": None}, "domicilio", "FORMATO", id="domicilio_null"),
    pytest.param(
        {"retencion_destajo_pct": "0.1234567"},
        "retencion_destajo_pct",
        "FORMATO",
        id="retencion_siete_decimales",
    ),
    pytest.param(
        {"retencion_destajo_pct": "abc"}, "retencion_destajo_pct", "FORMATO", id="retencion_texto"
    ),
    pytest.param(
        {"retencion_destajo_pct": "1e-1"},
        "retencion_destajo_pct",
        "FORMATO",
        id="retencion_exponente",
    ),
    pytest.param(
        {"retencion_destajo_pct": "٠.١"},
        "retencion_destajo_pct",
        "FORMATO",
        id="retencion_digitos_no_ascii",
    ),
    pytest.param(
        {"retencion_destajo_pct": "0.15\n"},
        "retencion_destajo_pct",
        "FORMATO",
        id="retencion_salto_de_linea_final",
    ),
    pytest.param(
        {"retencion_destajo_pct": 1}, "retencion_destajo_pct", "FORMATO", id="retencion_numero_json"
    ),
    pytest.param(
        {"retencion_destajo_pct": None}, "retencion_destajo_pct", "FORMATO", id="retencion_null"
    ),
    pytest.param({"fondo_garantia_pct": "abc"}, "fondo_garantia_pct", "FORMATO", id="fondo_texto"),
    pytest.param(
        {"fondo_garantia_pct": "0.0500001"},
        "fondo_garantia_pct",
        "FORMATO",
        id="fondo_siete_decimales",
    ),
    pytest.param(
        {"fondo_garantia_pct": "0.05\n"},
        "fondo_garantia_pct",
        "FORMATO",
        id="fondo_salto_de_linea_final",
    ),
    pytest.param(
        {"fondo_garantia_pct": 0.05}, "fondo_garantia_pct", "FORMATO", id="fondo_numero_json"
    ),
    pytest.param({"fondo_garantia_pct": None}, "fondo_garantia_pct", "FORMATO", id="fondo_null"),
    pytest.param({"umbral_alerta_pct": "abc"}, "umbral_alerta_pct", "FORMATO", id="umbral_texto"),
    pytest.param(
        {"umbral_alerta_pct": "0.1234567"},
        "umbral_alerta_pct",
        "FORMATO",
        id="umbral_siete_decimales",
    ),
    pytest.param(
        {"umbral_alerta_pct": "٠.١"}, "umbral_alerta_pct", "FORMATO", id="umbral_digitos_no_ascii"
    ),
    pytest.param(
        {"umbral_alerta_pct": "0.1\n"},
        "umbral_alerta_pct",
        "FORMATO",
        id="umbral_salto_de_linea_final",
    ),
    pytest.param({"umbral_alerta_pct": 1}, "umbral_alerta_pct", "FORMATO", id="umbral_numero_json"),
    pytest.param({"iva_acreditable": "yes"}, "iva_acreditable", "FORMATO", id="iva_cadena_yes"),
    pytest.param({"iva_acreditable": "true"}, "iva_acreditable", "FORMATO", id="iva_cadena_true"),
    pytest.param({"iva_acreditable": 1}, "iva_acreditable", "FORMATO", id="iva_entero_1"),
    pytest.param({"iva_acreditable": 0}, "iva_acreditable", "FORMATO", id="iva_entero_0"),
    pytest.param({"iva_acreditable": None}, "iva_acreditable", "FORMATO", id="iva_null"),
]


@pytest.mark.parametrize(("cuerpo", "campo", "codigo"), CASOS_DE_FORMA)
def test_tkt012b_ca3_api_patch_forma_invalida_responde_422_con_el_campo(
    cuerpo: dict[str, object],
    campo: str,
    codigo: str,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    fabricar_obra: Callable[..., uuid.UUID],
) -> None:
    """TC-44 · TC-45 · CA-3 — un cuerpo que no cumple la forma del contrato: `422` `VALIDACION` con el campo y el código.

    Una fila por defecto de `CA-3`: nombre y domicilio vacíos, en blanco, con `NUL` o con más del tope;
    porcentajes con más de seis decimales, texto, exponente, dígitos no ASCII, salto de línea final o
    número JSON; `iva_acreditable` que no es un booleano JSON. Solo `umbral_alerta_pct` admite `null`:
    en los demás campos es `422` señalando **ese** campo. Un `NUL` se rechaza aquí y no llega al motor
    (daría `500`). Un solo campo inválido a la vez; no se escribe nada.
    """
    usuario = abrir_sesion()
    obra_id = fabricar_obra()
    antes = _foto(base)

    respuesta = _patch(cliente, usuario, obra_id, cuerpo)

    _error_de_validacion(respuesta, campo, codigo)
    assert _foto(base) == antes


@pytest.mark.parametrize(
    ("campo", "valor", "mensaje"),
    [
        pytest.param(
            "retencion_destajo_pct",
            "-0.010000",
            MENSAJE_PORCENTAJE_FUERA_DE_RANGO,
            id="retencion_negativa",
        ),
        pytest.param(
            "retencion_destajo_pct",
            "1.000001",
            MENSAJE_PORCENTAJE_FUERA_DE_RANGO,
            id="retencion_sobre_uno",
        ),
        pytest.param(
            "fondo_garantia_pct",
            "-0.010000",
            MENSAJE_PORCENTAJE_FUERA_DE_RANGO,
            id="fondo_negativo",
        ),
        pytest.param(
            "fondo_garantia_pct",
            "1.000001",
            MENSAJE_PORCENTAJE_FUERA_DE_RANGO,
            id="fondo_sobre_uno",
        ),
        pytest.param(
            "umbral_alerta_pct", "-0.000001", MENSAJE_UMBRAL_NEGATIVO, id="umbral_negativo"
        ),
    ],
)
def test_tkt012b_ca3_api_patch_porcentaje_fuera_de_rango_responde_422(
    campo: str,
    valor: str,
    mensaje: str,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    fabricar_obra: Callable[..., uuid.UUID],
) -> None:
    """TC-26 · TC-44 · CA-3 · PA-02 · PA-18 — un porcentaje fuera de rango: `422` `FUERA_DE_RANGO` con el mensaje del alta.

    Retención y fondo de 0 a 1; el umbral, no negativo. El `422` lo da el caso de uso antes del motor: sin
    él, el `CHECK` de la tabla daría `23514` y un `500`. No se escribe nada.
    """
    usuario = abrir_sesion()
    obra_id = fabricar_obra()
    antes = _foto(base)

    respuesta = _patch(cliente, usuario, obra_id, {campo: valor})

    _error_de_validacion(respuesta, campo, "FUERA_DE_RANGO", mensaje)
    assert _foto(base) == antes


def test_tkt012b_ca3_api_patch_un_rechazo_no_deja_pasar_el_cambio_valido_del_mismo_cuerpo(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    fabricar_obra: Callable[..., uuid.UUID],
) -> None:
    """CA-3 — un cuerpo con un nombre válido y un fondo fuera de rango se rechaza entero: el nombre no cambia.

    La edición es todo o nada: el `422` por rango llega antes de la transacción y no hay escritura parcial
    ni asiento.
    """
    usuario = abrir_sesion()
    obra_id = fabricar_obra()
    antes = _foto(base)

    respuesta = _patch(
        cliente,
        usuario,
        obra_id,
        {"nombre": "Nombre que no debe guardarse", "fondo_garantia_pct": "1.500000"},
    )

    _error_de_validacion(
        respuesta, "fondo_garantia_pct", "FUERA_DE_RANGO", MENSAJE_PORCENTAJE_FUERA_DE_RANGO
    )
    assert _foto(base) == antes
    assert base.filas("SELECT nombre FROM obra WHERE id = %s", obra_id) == [(NOMBRE_INICIAL,)]


# --------------------------------------------------------------------------- CA-4


@pytest.mark.parametrize("rol", ROLES_QUE_OPERAN)
def test_tkt012b_ca4_api_patch_de_obra_cerrada_responde_409_con_el_estado(
    rol: str,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    fabricar_obra: Callable[..., uuid.UUID],
) -> None:
    """TC-25 · CA-4 — editar una obra `CERRADA`: `409` `CONFLICTO` `ESTADO_NO_PERMITE_OPERACION` con el estado en el detalle.

    Contrato completo: `tipo` `CONFLICTO` (nunca `REGLA_NEGOCIO`), el código del catálogo, el mensaje con
    el código de la obra y su estado, `detalle` con el estado actual y sin acciones (una obra cerrada no
    admite ninguna). La obra y la bitácora no cambian, aunque el cuerpo sea válido.
    """
    usuario = abrir_sesion((rol,))
    obra_id = fabricar_obra(estado="CERRADA")
    antes = _foto(base)

    respuesta = _patch(cliente, usuario, obra_id, {"nombre": "Nombre que no debe guardarse"})

    _exigir_estado_no_permite(respuesta, obra_id, estado="CERRADA", con_operaciones=False)
    assert _foto(base) == antes
    assert _asientos(base, obra_id) == []


# --------------------------------------------------------------------------- TC-46 · CA-5


@pytest.mark.parametrize("rol", ROLES_QUE_OPERAN)
def test_hdu001_esc20_api_delete_de_obra_sin_historial_responde_204_y_asienta(
    rol: str,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    fabricar_obra: Callable[..., uuid.UUID],
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """HDU-001 esc. 20 · TC-46 · CA-5 · RN-01 — `204` sin cuerpo, la obra desaparece y la bitácora conserva su código y su nombre.

    Una obra recién dada de alta en `PLANEACION`, sin línea base ni importaciones. Responde `204` sin
    cuerpo; la fila ya no existe, `GET /obras` ya no la trae y `GET /obras/{id}` responde `404`. El
    asiento `ELIMINAR` sobrevive a la obra (`bitacora.obra_id` no tiene clave foránea) con quién, cuándo y
    la fotografía de la obra. Otra obra, también sin historial, no se toca.
    """
    usuario = abrir_sesion((rol,))
    obra_id = fabricar_obra(codigo="AP-099-26", estado="PLANEACION")
    otra = fabricar_obra(codigo="AP-098-26", estado="PLANEACION")
    otra_antes = _fila_de_obra(base, otra)

    respuesta = _borrar(cliente, usuario, obra_id)

    assert respuesta.status_code == 204, respuesta.text
    assert respuesta.content == b""
    assert base.filas("SELECT id FROM obra WHERE id = %s", obra_id) == []
    asientos = _asientos(base, obra_id)
    assert [fila[:7] for fila in asientos] == [
        ("ELIMINAR", "obra", obra_id, usuario.usuario_id, reloj_de_prueba.ahora, None, obra_id)
    ]
    assert asientos[0][7]["codigo"] == "AP-099-26"
    assert asientos[0][7]["nombre"] == "Obra AP-099-26"
    assert _fila_de_obra(base, otra) == otra_antes
    lista = _leer(cliente, usuario, RUTA)
    assert lista.status_code == 200, lista.text
    assert [obra["codigo"] for obra in lista.json()["elementos"]] == ["AP-098-26"]
    assert _leer(cliente, usuario, _ruta(obra_id)).status_code == 404


def test_tkt012b_ca5_api_delete_libera_el_codigo_para_un_alta_nueva(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    fabricar_obra: Callable[..., uuid.UUID],
) -> None:
    """TC-INV-5 · CA-5 — el código de una obra borrada queda libre: un `POST /obras` con el mismo código responde `201`.

    El borrado es físico (no libera el código un borrado lógico). La obra nueva es otra fila.
    """
    usuario = abrir_sesion()
    obra_id = fabricar_obra(codigo="AP-099-26", estado="PLANEACION")
    assert _borrar(cliente, usuario, obra_id).status_code == 204

    alta = _llamar(
        cliente,
        "POST",
        RUTA,
        usuario,
        {
            "codigo": "AP-099-26",
            "nombre": "Obra que reutiliza el código",
            "domicilio": "Calle de prueba 2",
            "tipo_contrato": TIPO_CONTRATO,
            "retencion_destajo_pct": "0.15",
            "fondo_garantia_pct": "0.05",
            "iva_acreditable": True,
        },
    )

    assert alta.status_code == 201, alta.text
    assert alta.json()["id"] != str(obra_id)
    assert base.filas("SELECT codigo FROM obra") == [("AP-099-26",)]


# --------------------------------------------------------------------------- TC-47 · CA-6


@pytest.mark.parametrize(
    ("estado", "historia"),
    [
        pytest.param("ACTIVA", "congelada", id="activa_con_linea_base_congelada"),
        pytest.param("PLANEACION", "borrador", id="planeacion_con_linea_base_borrador"),
        pytest.param("PLANEACION", "importaciones", id="planeacion_con_solo_importaciones"),
        pytest.param("SUSPENDIDA", "importaciones", id="suspendida_con_importaciones"),
        pytest.param("CERRADA", "importaciones", id="cerrada_con_importaciones"),
    ],
)
def test_hdu001_esc20_api_delete_con_historial_responde_409_completo_y_no_borra(
    estado: str,
    historia: str,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    fabricar_obra: Callable[..., uuid.UUID],
    datos_presupuesto: DatosPresupuesto,
) -> None:
    """HDU-001 esc. 20 · TC-47 · CA-6 · RN-01 — con historial: `409` `CONFLICTO` `OBRA_CON_HISTORIAL`, detalle con los conteos y acciones que el estado admite.

    La línea base congelada marca `linea_base_congelada`; una `BORRADOR` y las importaciones solas son
    historial igual (D-1) con `linea_base_congelada` falso. Las acciones son `SUSPENDER_OBRA` y
    `CERRAR_OBRA` con método `POST` y la ruta absoluta **de esa obra**, y solo las que el estado admite:
    desde `PLANEACION` y `SUSPENDIDA`, solo `CERRAR_OBRA`; desde `CERRADA`, ninguna (ofrecer una que
    respondería `409` es el defecto). La obra, su historia y la bitácora quedan intactas.
    """
    usuario = abrir_sesion()
    obra_id = fabricar_obra(estado=estado)
    otra = fabricar_obra(codigo="AP-777-26", estado=estado)
    _dar_historia(datos_presupuesto, obra_id, historia)
    antes = _foto(base)

    respuesta = _borrar(cliente, usuario, obra_id)

    _exigir_con_historial(respuesta, obra_id, estado=estado, detalle=HISTORIAS[historia])
    assert _foto(base) == antes
    assert base.filas("SELECT id FROM obra WHERE id IN (%s, %s) ORDER BY id", obra_id, otra) == (
        sorted([(obra_id,), (otra,)])
    )
    assert _asientos(base, obra_id) == []


def test_hdu001_esc20_api_delete_con_historial_responde_lo_mismo_a_direccion_general(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    fabricar_obra: Callable[..., uuid.UUID],
    datos_presupuesto: DatosPresupuesto,
) -> None:
    """TC-47 · CA-6 · CA-11 — las acciones del `409` se filtran por el rol de quien llama, y Dirección General las ve completas.

    Las dos acciones están declaradas para los dos roles que operan; el filtro por rol no se las quita a
    Dirección General. (Quien no opera no llega al `409`: recibe `403` antes, ver `CA-11`.)
    """
    usuario = abrir_sesion(("DIRECCION_GENERAL",))
    obra_id = fabricar_obra()
    _dar_historia(datos_presupuesto, obra_id, "congelada")

    respuesta = _borrar(cliente, usuario, obra_id)

    _exigir_con_historial(respuesta, obra_id, estado="ACTIVA", detalle=HISTORIAS["congelada"])
    assert [accion["clave"] for accion in respuesta.json()["acciones"]] == [
        "SUSPENDER_OBRA",
        "CERRAR_OBRA",
    ]


def test_hdu001_esc20_api_las_acciones_del_bloqueo_se_pueden_seguir_hasta_cerrar(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    fabricar_obra: Callable[..., uuid.UUID],
    datos_presupuesto: DatosPresupuesto,
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """HDU-001 esc. 20 · TC-47 · CA-6 · CA-8 — las acciones que ofrece el `409` son ejecutables tal cual vienen, y el bloqueo se actualiza con el estado.

    Se sigue `SUSPENDER_OBRA` con su método y su ruta (`200`, la obra queda `SUSPENDIDA`); el nuevo
    `DELETE` ofrece solo `CERRAR_OBRA`; se sigue esa (`200`, `CERRADA`); el tercer `DELETE` ya no ofrece
    nada. Ningún dato histórico se pierde en el camino. El reloj avanza un segundo entre las dos
    transiciones: con el reloj congelado los dos asientos compartirían `ocurrido_en` y su orden dependería
    del `id` aleatorio.
    """
    usuario = abrir_sesion()
    obra_id = fabricar_obra()
    _dar_historia(datos_presupuesto, obra_id, "congelada")
    lineas_base = base.filas("SELECT * FROM linea_base ORDER BY id")

    primer_bloqueo = _borrar(cliente, usuario, obra_id)
    assert primer_bloqueo.status_code == 409, primer_bloqueo.text
    suspender = primer_bloqueo.json()["acciones"][0]
    assert suspender["clave"] == "SUSPENDER_OBRA"
    suspendida = _llamar(
        cliente, suspender["metodo"], suspender["ruta"], usuario, {"motivo": "Obra detenida"}
    )
    assert suspendida.status_code == 200, suspendida.text
    assert suspendida.json()["estado"] == "SUSPENDIDA"
    reloj_de_prueba.avanzar(timedelta(seconds=1))

    segundo_bloqueo = _borrar(cliente, usuario, obra_id)
    _exigir_con_historial(
        segundo_bloqueo, obra_id, estado="SUSPENDIDA", detalle=HISTORIAS["congelada"]
    )
    cerrar = segundo_bloqueo.json()["acciones"][0]
    assert cerrar["clave"] == "CERRAR_OBRA"
    cerrada = _llamar(
        cliente, cerrar["metodo"], cerrar["ruta"], usuario, {"motivo": "Obra concluida"}
    )
    assert cerrada.status_code == 200, cerrada.text
    assert cerrada.json()["estado"] == "CERRADA"

    tercer_bloqueo = _borrar(cliente, usuario, obra_id)
    _exigir_con_historial(tercer_bloqueo, obra_id, estado="CERRADA", detalle=HISTORIAS["congelada"])
    assert tercer_bloqueo.json()["acciones"] == []
    assert base.filas("SELECT * FROM linea_base ORDER BY id") == lineas_base
    assert [fila[0] for fila in _asientos(base, obra_id)] == ["SUSPENDER", "CERRAR"]


def test_tkt012b_ca6_api_delete_con_una_fila_de_otro_modulo_responde_409_y_no_500(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    fabricar_obra: Callable[..., uuid.UUID],
    datos_presupuesto: DatosPresupuesto,
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """TC-32 · CA-6 · D-DIS-4 — una requisición que cuelga de la obra (sin fuente inyectada) es `409` `OBRA_CON_HISTORIAL`, nunca `500`.

    Ningún módulo publica todavía su fuente de historial, así que el conteo no ve la fila: la última
    barrera es la clave foránea `ON DELETE RESTRICT` (`23001`), que se traduce a `OBRA_CON_HISTORIAL` con
    el detalle del contrato (`movimientos` 1, sin el nombre de la restricción: CWE-209), no al
    `ESTADO_NO_PERMITE_OPERACION` genérico. Nada se borra ni se asienta
    (el asiento `ELIMINAR` se deshace con la transacción).
    """
    usuario = abrir_sesion()
    obra_id = fabricar_obra()
    base.ejecutar(
        "INSERT INTO requisicion (id, obra_id, tipo_partida_id, solicitante_id, estado, "
        "importe_solicitado, creado_en, actualizado_en) "
        "VALUES (%s, %s, %s, %s, 'BORRADOR', %s, %s, %s)",
        uuid.uuid4(),
        obra_id,
        datos_presupuesto.tipo_partida(),
        usuario.usuario_id,
        Decimal("1000.0000"),
        reloj_de_prueba.ahora,
        reloj_de_prueba.ahora,
    )
    antes = _foto(base)

    respuesta = _borrar(cliente, usuario, obra_id)

    _exigir_con_historial(
        respuesta,
        obra_id,
        estado="ACTIVA",
        detalle=_detalle_de_historial(movimientos=1),
    )
    assert _foto(base) == antes
    assert _asientos(base, obra_id) == []


# --------------------------------------------------------------------------- TC-48 · CA-8


TRANSICIONES_ADMITIDAS = [
    pytest.param("ACTIVA", "/suspension", "SUSPENDIDA", "SUSPENDER", id="activa_suspension"),
    pytest.param(
        "SUSPENDIDA", "/reactivacion", "ACTIVA", "REACTIVAR", id="suspendida_reactivacion"
    ),
    pytest.param("ACTIVA", "/cierre", "CERRADA", "CERRAR", id="activa_cierre"),
    pytest.param("SUSPENDIDA", "/cierre", "CERRADA", "CERRAR", id="suspendida_cierre"),
    pytest.param("PLANEACION", "/cierre", "CERRADA", "CERRAR", id="planeacion_cierre"),
]


@pytest.mark.parametrize("rol", ROLES_QUE_OPERAN)
@pytest.mark.parametrize(("origen", "sufijo", "destino", "verbo"), TRANSICIONES_ADMITIDAS)
def test_hdu001_esc20_api_transicion_admitida_responde_200_y_asienta_con_motivo(
    rol: str,
    origen: str,
    sufijo: str,
    destino: str,
    verbo: str,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    fabricar_obra: Callable[..., uuid.UUID],
    datos_presupuesto: DatosPresupuesto,
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """HDU-001 esc. 20 · TC-48 · CA-8 — suspender, reactivar y cerrar: `200` con la `Obra` en su destino y un asiento con el estado anterior y el motivo.

    Las cinco transiciones de `D-2` (incluida `PLANEACION` a `CERRADA`) para los dos roles que operan.
    La respuesta es la obra tal como la consulta `GET` la ve (con su línea base vigente), con el estado
    nuevo y sellada con quién y cuándo. El asiento lleva el verbo, el estado anterior y el nuevo y el
    motivo **sin espacios en los extremos**. Ningún dato histórico (línea base) se pierde y otra obra no se
    toca.
    """
    usuario = abrir_sesion((rol,))
    obra_id = fabricar_obra(estado=origen)
    otra = fabricar_obra(codigo="AP-777-26", estado=origen)
    datos_presupuesto.linea_base(
        estado="BORRADOR" if origen == "PLANEACION" else "CONGELADA", obra_id=obra_id
    )
    previa = _leer(cliente, usuario, _ruta(obra_id))
    assert previa.status_code == 200, previa.text
    lineas_base = base.filas("SELECT * FROM linea_base ORDER BY id")
    otra_antes = _fila_de_obra(base, otra)

    respuesta = _transicion(cliente, usuario, obra_id, sufijo, {"motivo": f"  {MOTIVO}  "})

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.headers["content-type"].startswith("application/json")
    cuerpo = respuesta.json()
    validar_contra("Obra", cuerpo)
    assert datetime.fromisoformat(cuerpo["actualizado_en"]) == reloj_de_prueba.ahora
    assert _sin_fechas(cuerpo) == {**_sin_fechas(previa.json()), "estado": destino}
    assert base.filas(
        "SELECT estado, actualizado_en, actualizado_por_id FROM obra WHERE id = %s", obra_id
    ) == [(destino, reloj_de_prueba.ahora, usuario.usuario_id)]
    assert _asientos(base, obra_id) == [
        (
            verbo,
            "obra",
            obra_id,
            usuario.usuario_id,
            reloj_de_prueba.ahora,
            MOTIVO,
            obra_id,
            {"estado": origen},
            {"estado": destino},
        )
    ]
    assert base.filas("SELECT * FROM linea_base ORDER BY id") == lineas_base
    assert _fila_de_obra(base, otra) == otra_antes


RECHAZOS_DE_TRANSICION = [
    pytest.param("PLANEACION", "/suspension", id="planeacion_suspension"),
    pytest.param("PLANEACION", "/reactivacion", id="planeacion_reactivacion"),
    pytest.param("ACTIVA", "/reactivacion", id="activa_reactivacion"),
    pytest.param("SUSPENDIDA", "/suspension", id="suspendida_suspension"),
    pytest.param("CERRADA", "/suspension", id="cerrada_suspension"),
    pytest.param("CERRADA", "/reactivacion", id="cerrada_reactivacion"),
    pytest.param("CERRADA", "/cierre", id="cerrada_cierre"),
]


@pytest.mark.parametrize("rol", ROLES_QUE_OPERAN)
@pytest.mark.parametrize(("origen", "sufijo"), RECHAZOS_DE_TRANSICION)
def test_tkt012b_ca9_api_transicion_no_admitida_responde_409_con_estado_y_operaciones(
    rol: str,
    origen: str,
    sufijo: str,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    fabricar_obra: Callable[..., uuid.UUID],
) -> None:
    """TC-35 · TC-48 · CA-9 · D-2 — las siete combinaciones prohibidas: `409` `CONFLICTO` `ESTADO_NO_PERMITE_OPERACION` con el estado actual y las operaciones que sí admite.

    Contrato completo: el mensaje con el código y el estado, el detalle con `estado` y
    `operaciones_admitidas` (en el orden `SUSPENDER`, `REACTIVAR`, `CERRAR`) y una acción `POST` por cada
    operación admitida con la ruta real de esa obra, y **solo** esas (nunca una que respondería `409`).
    Los dos roles que operan ven las mismas acciones. La obra y la bitácora no cambian.
    """
    usuario = abrir_sesion((rol,))
    obra_id = fabricar_obra(estado=origen)
    antes = _foto(base)

    respuesta = _transicion(cliente, usuario, obra_id, sufijo, {"motivo": MOTIVO})

    _exigir_estado_no_permite(respuesta, obra_id, estado=origen, con_operaciones=True)
    assert _foto(base) == antes
    assert _asientos(base, obra_id) == []


# --------------------------------------------------------------------------- TC-36 · CA-10


CASOS_DE_MOTIVO = [
    pytest.param({}, ("motivo", "OBLIGATORIO"), id="motivo_ausente"),
    pytest.param({"motivo": ""}, ("motivo", "OBLIGATORIO"), id="motivo_vacio"),
    pytest.param({"motivo": "   "}, ("motivo", "OBLIGATORIO"), id="motivo_en_blanco"),
    pytest.param({"motivo": "m" * 2001}, ("motivo", "DEMASIADO_LARGO"), id="motivo_de_2001"),
    pytest.param({"motivo": "a\u0000b"}, ("motivo", "FORMATO"), id="nul_en_motivo"),
    pytest.param({"motivo": 123}, ("motivo", "FORMATO"), id="motivo_numero_json"),
    pytest.param({"motivo": None}, ("motivo", "FORMATO"), id="motivo_null"),
    pytest.param([], ("cuerpo", "FORMATO"), id="cuerpo_que_no_es_objeto"),
    pytest.param(b"null", ("cuerpo", "FORMATO"), id="cuerpo_null"),
]


@pytest.mark.parametrize("operacion", OPERACIONES_POST, ids=lambda operacion: operacion.nombre)
@pytest.mark.parametrize(("cuerpo", "esperado"), CASOS_DE_MOTIVO)
def test_tkt012b_ca10_api_transicion_sin_motivo_valido_responde_422_en_motivo(
    operacion: Operacion,
    cuerpo: object,
    esperado: tuple[str, str],
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    fabricar_obra: Callable[..., uuid.UUID],
) -> None:
    """TC-36 · CA-10 — el motivo falta, está vacío, en blanco, pasa de 2000, lleva `NUL` o no es cadena: `422` `VALIDACION` señalando `motivo`.

    Las tres transiciones, sobre una obra en un estado que sí las admite: el `422` no es un `409`
    disfrazado. Sin la validación de `Motivo`, un `NUL` llegaría a `psycopg` y daría `500`. La obra y la
    bitácora no cambian.
    """
    usuario = abrir_sesion()
    obra_id = fabricar_obra(estado=operacion.estado)
    antes = _foto(base)

    respuesta = _transicion(cliente, usuario, obra_id, operacion.sufijo, cuerpo)

    _error_de_validacion(respuesta, *esperado)
    assert _foto(base) == antes
    assert _asientos(base, obra_id) == []


@pytest.mark.parametrize("operacion", OPERACIONES_POST, ids=lambda operacion: operacion.nombre)
def test_tkt012b_ca10_api_transicion_motivo_en_el_limite_y_recortado(
    operacion: Operacion,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    fabricar_obra: Callable[..., uuid.UUID],
) -> None:
    """CA-10 — un motivo de 2000 caracteres exactos pasa y los espacios de los extremos se recortan antes de asentar.

    El borde del tope es 2000 tras recortar: `"  " + "m" * 2000 + "  "` se asienta como 2000 caracteres.
    """
    usuario = abrir_sesion()
    obra_id = fabricar_obra(estado=operacion.estado)

    respuesta = _transicion(
        cliente, usuario, obra_id, operacion.sufijo, {"motivo": "  " + "m" * 2000 + "  "}
    )

    assert respuesta.status_code == 200, respuesta.text
    assert base.filas("SELECT motivo FROM bitacora WHERE entidad_id = %s", obra_id) == [
        ("m" * 2000,)
    ]


# --------------------------------------------------------------------------- TC-50 · CA-11


@pytest.mark.parametrize("operacion", OPERACIONES, ids=lambda operacion: operacion.nombre)
@pytest.mark.parametrize("rol", ROLES_SIN_ESCRITURA)
def test_tkt012b_ca11_api_sin_permiso_responde_403_sin_cifras_y_asienta_denegar(
    rol: str,
    operacion: Operacion,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    fabricar_obra: Callable[..., uuid.UUID],
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """TC-50 · CA-11 · RN-25 — Compras, Almacén, Residente y Administración: `403` `PERMISO` `ROL_INSUFICIENTE` en las cinco, sin cifras del recurso y con su `DENEGAR`.

    Leen obras pero no las mantienen. El cuerpo no trae `detalle` ni el código, el nombre, el domicilio o
    los porcentajes de la obra; el intento queda asentado como `DENEGAR` a nombre de quien llamó, con el
    método y la ruta concretos y los roles exigidos. La obra y su bitácora no cambian, con una petición
    que de otro modo habría procedido.
    """
    usuario = abrir_sesion((rol,))
    obra_id = fabricar_obra(estado=operacion.estado)
    antes = _foto(base)

    respuesta = _pedir(cliente, operacion, obra_id, usuario)

    cuerpo = exigir_error(
        respuesta,
        estado=403,
        esperado={
            "tipo": "PERMISO",
            "motivo": "ROL_INSUFICIENTE",
            "mensaje": MENSAJE_ROL_INSUFICIENTE,
            "roles_requeridos": ROLES_QUE_OPERAN,
        },
        esquema="ErrorPermiso",
    )
    assert "detalle" not in cuerpo
    for cifra in (CODIGO, NOMBRE_INICIAL, DOMICILIO_INICIAL, "0.150000", "0.050000", "0.100000"):
        assert cifra not in respuesta.text, cifra
    assert _foto(base) == antes
    exigir_denegacion(
        base,
        metodo=operacion.metodo,
        usuario_id=usuario.usuario_id,
        ocurrido_en=reloj_de_prueba.ahora,
        motivo="ROL_INSUFICIENTE",
        ruta=_ruta(obra_id, operacion.sufijo),
        roles_requeridos=ROLES_QUE_OPERAN,
    )


@pytest.mark.parametrize("operacion", OPERACIONES, ids=lambda operacion: operacion.nombre)
def test_tkt012b_ca11_api_sin_permiso_sobre_obra_inexistente_responde_403_no_404(
    operacion: Operacion,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    fabricar_obra: Callable[..., uuid.UUID],
) -> None:
    """CA-11 · CA-12 · conv-seguridad — quien no puede operar recibe `403` aunque la obra no exista: el `404` no revela qué obras hay.

    El rol se comprueba antes de buscar la obra. Un `404` para el rol sin permiso y un `403` para el
    resto delataría la existencia de la obra.
    """
    usuario = abrir_sesion(("ALMACEN",))
    fabricar_obra(estado=operacion.estado)
    antes = _foto(base)

    respuesta = _pedir(cliente, operacion, uuid.uuid4(), usuario)

    exigir_error(
        respuesta,
        estado=403,
        esperado={
            "tipo": "PERMISO",
            "motivo": "ROL_INSUFICIENTE",
            "mensaje": MENSAJE_ROL_INSUFICIENTE,
            "roles_requeridos": ROLES_QUE_OPERAN,
        },
        esquema="ErrorPermiso",
    )
    assert _foto(base) == antes


# --------------------------------------------------------------------------- TC-49 · TC-51 · CA-11


@pytest.mark.parametrize("operacion", OPERACIONES, ids=lambda operacion: operacion.nombre)
@pytest.mark.parametrize(("cookie", "cabecera"), SIN_PAR_VALIDO)
def test_tkt012b_ca11_api_sin_sesion_y_sin_csrf(
    cookie: str | None,
    cabecera: str | None,
    operacion: Operacion,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    fabricar_obra: Callable[..., uuid.UUID],
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """TC-49 · TC-51 · CA-11 · RNF-05 — sin sesión `401` `SESION`; con sesión de Director de Proyectos y sin el doble envío, `403` `ORIGEN_NO_VERIFICADO` con su `DENEGAR`.

    Las cinco operaciones con las cuatro combinaciones de `CA-9` de TKT-057 (`SIN_PAR_VALIDO`). Sin sesión
    responde `401` aunque el par sea válido, y una denegación anónima no se asienta. Con sesión y sin par,
    la petición no se ejecuta aunque quien llama pueda operar y aunque el cuerpo sea válido y la obra esté
    en un estado que la admitiría. En los dos casos la obra y la bitácora quedan como estaban.
    """
    director = abrir_sesion()
    obra_id = fabricar_obra(estado=operacion.estado)
    antes = _foto(base)

    anonima = _pedir(cliente, operacion, obra_id, None)
    exigir_error(
        anonima,
        estado=401,
        esperado={"tipo": "SESION", "motivo": "SIN_SESION", "mensaje": MENSAJE_SIN_SESION},
        esquema="ErrorSesion",
    )
    assert _foto(base) == antes
    assert _cuenta(base, "SELECT count(*) FROM bitacora WHERE accion = 'DENEGAR'") == 0

    respuesta = _pedir(
        cliente, operacion, obra_id, director, cookie_csrf=cookie, cabecera_csrf=cabecera
    )

    exigir_error(
        respuesta,
        estado=403,
        esperado={
            "tipo": "PERMISO",
            "motivo": "ORIGEN_NO_VERIFICADO",
            "mensaje": MENSAJE_ORIGEN_NO_VERIFICADO,
            "roles_requeridos": [],
        },
        esquema="ErrorPermiso",
    )
    assert _foto(base) == antes
    exigir_denegacion(
        base,
        metodo=operacion.metodo,
        usuario_id=director.usuario_id,
        ocurrido_en=reloj_de_prueba.ahora,
        motivo="ORIGEN_NO_VERIFICADO",
        ruta=_ruta(obra_id, operacion.sufijo),
        roles_requeridos=[],
    )


@pytest.mark.parametrize("operacion", OPERACIONES, ids=lambda operacion: operacion.nombre)
def test_tkt012b_ca11_api_el_origen_se_verifica_antes_que_el_rol(
    operacion: Operacion,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    fabricar_obra: Callable[..., uuid.UUID],
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """CA-11 · conv-seguridad — quien no tiene el rol y tampoco manda el par recibe el `403` de origen, no el de rol.

    `verificar_origen` va antes que `exigir_rol` en las cinco rutas; un solo `DENEGAR` con motivo
    `ORIGEN_NO_VERIFICADO`. Con el orden invertido el motivo sería `ROL_INSUFICIENTE`.
    """
    usuario = abrir_sesion(("COMPRAS",))
    obra_id = fabricar_obra(estado=operacion.estado)

    respuesta = _pedir(cliente, operacion, obra_id, usuario, cookie_csrf=None, cabecera_csrf=None)

    exigir_error(
        respuesta,
        estado=403,
        esperado={
            "tipo": "PERMISO",
            "motivo": "ORIGEN_NO_VERIFICADO",
            "mensaje": MENSAJE_ORIGEN_NO_VERIFICADO,
            "roles_requeridos": [],
        },
        esquema="ErrorPermiso",
    )
    exigir_denegacion(
        base,
        metodo=operacion.metodo,
        usuario_id=usuario.usuario_id,
        ocurrido_en=reloj_de_prueba.ahora,
        motivo="ORIGEN_NO_VERIFICADO",
        ruta=_ruta(obra_id, operacion.sufijo),
        roles_requeridos=[],
    )


@pytest.mark.parametrize("operacion", OPERACIONES, ids=lambda operacion: operacion.nombre)
def test_tkt012b_api_la_ruta_es_def_con_sesion_y_origen_antes_que_el_rol(
    operacion: Operacion, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CA-11 · regla 11 · RNF-05 — cada una de las cinco rutas existe una sola vez, es `def`, exige sesión y rol y verifica el origen antes que el rol.

    Los recorridos de `test_tkt006_enrutador.py` y `test_tkt057_csrf.py` ven las rutas de la aplicación
    completa. Mutantes: ruta sin `verificar_origen`, `async def` o `exigir_rol` antes que
    `verificar_origen`.
    """
    aplicacion = construir_aplicacion(monkeypatch)
    camino = f"{RUTA}/{{obra_id}}{operacion.sufijo}"
    halladas = [
        r
        for r in rutas_de(aplicacion.routes)
        if r.path == camino and operacion.metodo in (r.methods or ())
    ]
    assert len(halladas) == 1, (
        f"Debe haber exactamente un {operacion.metodo} {camino}; hay {len(halladas)}"
    )
    ruta = halladas[0]

    assert inspect.isfunction(ruta.endpoint)
    assert not inspect.iscoroutinefunction(ruta.endpoint)
    assert sesion_vigente in list(llamadas(ruta.dependant))
    declaradas = [sub.call for sub in ruta.dependant.dependencies]
    roles = [
        posicion
        for posicion, llamada in enumerate(declaradas)
        if getattr(llamada, "__name__", "") == "comprobar_rol"
    ]
    assert len(roles) == 1, f"{ruta.path} debe declarar exactamente un exigir_rol"
    assert verificar_origen in declaradas, f"{ruta.path} debe declarar verificar_origen"
    assert declaradas.index(verificar_origen) < roles[0]


# --------------------------------------------------------------------------- TC-52 · CA-12


@pytest.mark.parametrize("operacion", OPERACIONES, ids=lambda operacion: operacion.nombre)
def test_tkt012b_ca12_api_obra_inexistente_responde_404_y_mal_formada_422(
    operacion: Operacion,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    fabricar_obra: Callable[..., uuid.UUID],
) -> None:
    """TC-52 · CA-12 — un UUID que no existe: `404` `NO_ENCONTRADO` con `recurso` `obra` y sin asiento; uno que no es UUID: `422` `VALIDACION` en `obra_id`.

    Hay una obra real, para que el `404` sea por el id y no por tabla vacía. El `404` es el de `obra` (no
    el de ruta inexistente, que es lo que responde un enrutador sin la ruta, con la ruta como recurso).
    Ninguno cambia la base.
    """
    usuario = abrir_sesion()
    fabricar_obra(estado=operacion.estado)
    antes = _foto(base)

    inexistente = _pedir(cliente, operacion, uuid.uuid4(), usuario)
    exigir_error(
        inexistente,
        estado=404,
        esperado={"tipo": "NO_ENCONTRADO", "mensaje": MENSAJE_OBRA_NO_EXISTE, "recurso": "obra"},
        esquema="ErrorNoEncontrado",
    )
    assert _foto(base) == antes

    mal_formada = _pedir(cliente, operacion, "no-es-uuid", usuario)
    _error_de_validacion(mal_formada, "obra_id", "FORMATO")
    assert _foto(base) == antes


# --------------------------------------------------------------------------- TC-53 (parte publicada)


def _tipos_no_nulos(contrato: dict[str, Any], nodo: dict[str, Any]) -> set[str]:
    """Los tipos de un nodo de esquema, con `$ref` resueltos y sin `null` (Pydantic publica `anyOf` con `null`)."""
    resuelto = resolver(contrato, nodo)
    variantes = resuelto.get("anyOf") or resuelto.get("oneOf")
    if variantes is not None:
        return set().union(*(_tipos_no_nulos(contrato, variante) for variante in variantes))
    tipo = resuelto.get("type")
    return set() if tipo in (None, "null") else {str(tipo)}


def test_tkt012b_api_las_cinco_operaciones_estan_en_el_contrato_publicado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-53 (parte publicada) · DoD — las cinco operaciones salen en `/openapi.json` con su `operationId`, `sesion` y `csrf`, su cuerpo y su respuesta.

    El borrador `docs/api/openapi.yaml` y los tipos del cliente son de la fila A8: aquí solo se exige lo
    que el servidor publica. `PATCH` recibe `ObraCambios` y responde `Obra`; las tres transiciones reciben
    `Motivo` y responden `Obra`; `DELETE` responde `204` sin cuerpo y no recibe ninguno. `obra_id` es el
    UUID de ruta del borrador. `ObraCambios` publica solo los seis campos editables, ninguno obligatorio,
    y **cierra** los desconocidos (`additionalProperties: false`): es lo que hace de `codigo`,
    `tipo_contrato` y `estado` un `422`.
    """
    contrato = contrato_publicado(monkeypatch)
    comparable = borrador_comparable()
    esperadas = [
        ("patch", "", "actualizar_obra"),
        ("delete", "", "eliminar_obra"),
        ("post", "/suspension", "suspender_obra"),
        ("post", "/reactivacion", "reactivar_obra"),
        ("post", "/cierre", "cerrar_obra"),
    ]
    for metodo, sufijo, identificador in esperadas:
        ruta = f"{RUTA}/{{obra_id}}{sufijo}"
        assert ruta in contrato["paths"], f"El contrato publicado no trae {ruta}"
        publicada = contrato["paths"][ruta].get(metodo)
        assert publicada is not None, f"El contrato publicado no trae {metodo.upper()} {ruta}"
        assert publicada["operationId"] == identificador
        exigidos = {nombre for requisito in publicada.get("security", []) for nombre in requisito}
        assert {"sesion", "csrf"} <= exigidos, identificador
        assert parametros_de(contrato, ruta, metodo) == parametros_de(
            comparable, f"/obras/{{obra_id}}{sufijo}", metodo
        ), identificador
        if metodo == "delete":
            assert "204" in publicada["responses"], identificador
            assert "200" not in publicada["responses"], identificador
            assert "content" not in publicada["responses"]["204"], identificador
            assert "requestBody" not in publicada, identificador
        else:
            assert publicada["responses"]["200"]["content"]["application/json"]["schema"] == {
                "$ref": "#/components/schemas/Obra"
            }, identificador
            cuerpo = "ObraCambios" if metodo == "patch" else "Motivo"
            assert publicada["requestBody"]["content"]["application/json"]["schema"] == {
                "$ref": f"#/components/schemas/{cuerpo}"
            }, identificador

    cambios = contrato["components"]["schemas"]["ObraCambios"]
    assert set(cambios["properties"]) == {
        "nombre",
        "domicilio",
        "retencion_destajo_pct",
        "fondo_garantia_pct",
        "iva_acreditable",
        "umbral_alerta_pct",
    }
    assert not cambios.get("required"), "Ningún campo de ObraCambios es obligatorio"
    assert cambios.get("additionalProperties") is False
    for campo in ("retencion_destajo_pct", "fondo_garantia_pct", "umbral_alerta_pct"):
        assert _tipos_no_nulos(contrato, cambios["properties"][campo]) == {"string"}, campo
    assert _tipos_no_nulos(contrato, cambios["properties"]["iva_acreditable"]) == {"boolean"}


# --------------------------------------------------------------------------- F001 · CWE-209 · ningún rechazo publica estructura interna


@dataclass(frozen=True)
class CasoDeRechazo:
    """Una petición que las cinco operaciones rechazan con un código 4xx, y lo que la provoca."""

    metodo: str
    sufijo: str
    cuerpo: object
    esperado: int
    estado: str = "ACTIVA"
    historia: str | None = None
    rol: str = "DIRECTOR_PROYECTOS"
    con_sesion: bool = True
    obra_existe: bool = True


ESQUEMA_DE_ERROR = {
    401: "ErrorSesion",
    403: "ErrorPermiso",
    404: "ErrorNoEncontrado",
    409: "ErrorConflictoEstado",
    422: "ErrorValidacion",
}
CLAVES_DEL_DETALLE_CON_HISTORIAL = {
    "linea_base_congelada",
    "lineas_base",
    "importaciones",
    "movimientos",
}
CASOS_DE_RECHAZO = [
    pytest.param(
        CasoDeRechazo("PATCH", "", {"nombre": "Nuevo nombre"}, 409, estado="CERRADA"),
        id="patch_409_obra_cerrada",
    ),
    pytest.param(CasoDeRechazo("PATCH", "", {"codigo": "AP-1-26"}, 422), id="patch_422_campo_fijo"),
    pytest.param(
        CasoDeRechazo("PATCH", "", {"nombre": "Nuevo nombre"}, 404, obra_existe=False),
        id="patch_404_obra_inexistente",
    ),
    pytest.param(
        CasoDeRechazo("PATCH", "", {"nombre": "Nuevo nombre"}, 403, rol="RESIDENTE"),
        id="patch_403_rol",
    ),
    pytest.param(
        CasoDeRechazo("PATCH", "", {"nombre": "Nuevo nombre"}, 401, con_sesion=False),
        id="patch_401_sin_sesion",
    ),
    pytest.param(
        CasoDeRechazo("DELETE", "", SIN_CUERPO, 409, historia="congelada"),
        id="delete_409_linea_base_congelada",
    ),
    pytest.param(
        CasoDeRechazo("DELETE", "", SIN_CUERPO, 409, historia="importaciones"),
        id="delete_409_importaciones",
    ),
    pytest.param(
        CasoDeRechazo("DELETE", "", SIN_CUERPO, 409, historia="otro_modulo"),
        id="delete_409_fila_de_otro_modulo_23001",
    ),
    pytest.param(
        CasoDeRechazo("DELETE", "", SIN_CUERPO, 404, obra_existe=False),
        id="delete_404_obra_inexistente",
    ),
    pytest.param(CasoDeRechazo("DELETE", "", SIN_CUERPO, 403, rol="COMPRAS"), id="delete_403_rol"),
    pytest.param(
        CasoDeRechazo("DELETE", "", SIN_CUERPO, 401, con_sesion=False), id="delete_401_sin_sesion"
    ),
    pytest.param(
        CasoDeRechazo("POST", "/suspension", {"motivo": MOTIVO}, 409, estado="SUSPENDIDA"),
        id="suspension_409_ya_suspendida",
    ),
    pytest.param(
        CasoDeRechazo("POST", "/reactivacion", {"motivo": MOTIVO}, 409, estado="ACTIVA"),
        id="reactivacion_409_no_suspendida",
    ),
    pytest.param(
        CasoDeRechazo("POST", "/cierre", {"motivo": MOTIVO}, 409, estado="CERRADA"),
        id="cierre_409_ya_cerrada",
    ),
    pytest.param(
        CasoDeRechazo("POST", "/suspension", {"motivo": ""}, 422), id="suspension_422_motivo_vacio"
    ),
    pytest.param(
        CasoDeRechazo("POST", "/reactivacion", {"motivo": MOTIVO}, 404, obra_existe=False),
        id="reactivacion_404_obra_inexistente",
    ),
    pytest.param(
        CasoDeRechazo("POST", "/cierre", {"motivo": MOTIVO}, 403, rol="ALMACEN"),
        id="cierre_403_rol",
    ),
    pytest.param(
        CasoDeRechazo("POST", "/cierre", {"motivo": MOTIVO}, 401, con_sesion=False),
        id="cierre_401_sin_sesion",
    ),
]


@pytest.mark.parametrize("caso", CASOS_DE_RECHAZO)
def test_tkt012b_ca6_api_ningun_rechazo_publica_estructura_interna(
    caso: CasoDeRechazo,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    fabricar_obra: Callable[..., uuid.UUID],
    datos_presupuesto: DatosPresupuesto,
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """F001 · CWE-209 · CA-6 — ningún `4xx` de las cinco operaciones nombra una restricción ni una clave foránea.

    Cada rechazo del borrador (`401`, `403`, `404`, `409`, `422`) se provoca contra cada operación y el
    cuerpo entero, en texto, no contiene `fk_` ni `restriccion`; el cuerpo valida contra el esquema de
    error del borrador y, si es `OBRA_CON_HISTORIAL`, su detalle son exactamente las cuatro claves del
    contrato con sus tipos (un `bool` y tres enteros no negativos). El caso `23001` (una requisición que
    cuelga de la obra y que ninguna fuente cuenta) es el que filtraba el nombre de la restricción.
    """
    usuario = abrir_sesion((caso.rol,))
    obra_id = fabricar_obra(estado=caso.estado)
    if caso.historia == "otro_modulo":
        base.ejecutar(
            "INSERT INTO requisicion (id, obra_id, tipo_partida_id, solicitante_id, estado, "
            "importe_solicitado, creado_en, actualizado_en) "
            "VALUES (%s, %s, %s, %s, 'BORRADOR', %s, %s, %s)",
            uuid.uuid4(),
            obra_id,
            datos_presupuesto.tipo_partida(),
            usuario.usuario_id,
            Decimal("1000.0000"),
            reloj_de_prueba.ahora,
            reloj_de_prueba.ahora,
        )
    elif caso.historia is not None:
        _dar_historia(datos_presupuesto, obra_id, caso.historia)

    respuesta = _llamar(
        cliente,
        caso.metodo,
        _ruta(obra_id if caso.obra_existe else uuid.uuid4(), caso.sufijo),
        usuario if caso.con_sesion else None,
        caso.cuerpo,
    )

    assert respuesta.status_code == caso.esperado, respuesta.text
    texto = respuesta.text.lower()
    assert "fk_" not in texto, respuesta.text
    assert "restriccion" not in texto and "restricción" not in texto, respuesta.text
    cuerpo = respuesta.json()
    validar_contra(ESQUEMA_DE_ERROR[caso.esperado], cuerpo)
    if cuerpo.get("codigo") == "OBRA_CON_HISTORIAL":
        detalle = cuerpo["detalle"]
        assert set(detalle) == CLAVES_DEL_DETALLE_CON_HISTORIAL, detalle
        assert isinstance(detalle["linea_base_congelada"], bool)
        for clave in ("lineas_base", "importaciones", "movimientos"):
            assert isinstance(detalle[clave], int) and not isinstance(detalle[clave], bool), detalle
            assert detalle[clave] >= 0, detalle
