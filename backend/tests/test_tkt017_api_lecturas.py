"""API de las lecturas de la línea base, fila B4 de TKT-017b2: cuatro `GET` de `presupuesto`.

Cubre TC-B13, TC-B14, TC-B16, TC-B17 y la parte de B4 de TC-B19 del diseño (`CA-B8`, `CA-B9`, `CA-R1`;
`HDU-001` esc. 14; `RN-01`, `RN-24`) contra PostgreSQL migrado con `alembic upgrade head` y el rol de
aplicación, por la aplicación real (`crear_aplicacion`) y un `TestClient` HTTPS:

- `GET /api/v1/obras/{obra_id}/lineas-base` (`listar_lineas_base`),
- `GET /api/v1/lineas-base/{linea_base_id}` (`obtener_linea_base`),
- `GET /api/v1/lineas-base/{linea_base_id}/conceptos` (`listar_conceptos_linea_base`),
- `GET /api/v1/lineas-base/{linea_base_id}/explosion` (`obtener_explosion_insumos`).

El libro real sale de la confirmación (`materializar_importacion`) y del congelado de la aplicación
(`congelar_linea_base`) con el libro `preparacion_dos_niveles` (12 apariciones de `620040-A`, seis en MUROS
y seis en PLAFONES_Y_CAJILLOS). Los casos que necesitan texto, códigos y cifras a medida (`q` con `%` y `_`,
escalas de la explosión) siembran a mano una línea base `BORRADOR` con sus copias y la congelan con `UPDATE`,
como hace el congelado real. Las respuestas se validan contra los esquemas del borrador y los valores se
comparan campo por campo; los importes viajan como cadena con su escala (cantidad 4 decimales, precio 4,
importe 4, rendimiento 6).

Cada rechazo comprueba el contrato de error completo, no solo el código: `tipo`, `motivo` o `recurso`,
`mensaje` literal, las claves exactas del cuerpo, `correlacion_id` igual a la cabecera `X-Correlacion-Id` y la
validez contra el esquema de error del borrador. Los `403` verifican además el asiento `DENEGAR` y que el
cuerpo no trae importes ni identificadores del recurso.

Rojo original de B4: cuando se escribió este archivo, las cuatro rutas `GET` no existían (salvo la lógica
mínima de `obtener_linea_base` de B3, que ninguna ruta exponía), así que el enrutador respondía `404`
(`NO_ENCONTRADO` con la ruta como recurso) donde cada prueba espera `200`, `401`, `403`, `404` del recurso
o `422`. Riesgo `R-2` (aceptado por la persona dueña): lo que no exista se importa dentro del cuerpo de cada
prueba y la recolección nunca falla.

Mutantes que este archivo debe poner en rojo: `M-B8` en su variante de b2 (`importes_venta_por_tipo` suma
`partida_concepto` también en una `CONGELADA`: `test_hdu001_esc14_lecturas_de_una_congelada_ignoran_...`);
«la lectura de conceptos sale de `partida_concepto`» (la misma prueba, por el importe de los doce
conceptos); «`q` sin `autoescape`» (`test_hdu001_esc14_conceptos_q_...`); «conceptos o explosión con
contenido en `BORRADOR`» (`test_hdu001_esc14_lecturas_de_un_borrador`); «`importe_total` redondeado o
calculado sobre todo el conjunto en lugar de los renglones devueltos» (`test_hdu001_esc14_explosion_...`);
«`GET` con `verificar_origen`» (`test_tkt017_cab08_las_lecturas_no_exigen_csrf`); «`GET` sin `exigir_rol`»
(`test_tkt017_cab08_lecturas_sin_rol`).

TC-B17 y las rutas existentes. `test_tkt006_enrutador.py` ya recorre las rutas `GET` con `exigir_rol`
(`violaciones` mira la cadena de dependencias de toda la aplicación) y `test_tkt057_csrf.py` solo mira las
que mutan (y TC-49 exige que ninguna `GET` declare `csrf`): las cuatro rutas nuevas quedan cubiertas sin
cambiar esos archivos, y ninguna lista cerrada necesita una entrada nueva. Aquí las protegen
`test_tkt017_car1_las_rutas_de_lectura_...` (están en el recorrido, son `def`, llevan `sesion_vigente` y un
solo `exigir_rol`, y ninguna lleva `verificar_origen`) y `test_tkt017_car1_openapi_publica_las_lecturas_...`.

El MVP no tiene permiso por obra (`docs/07-especificacion-api.md`, línea 399): el caso «otra obra» de la lista
del tester de API no aplica a estas rutas. Lo que sí se prueba es que `listar_lineas_base` de una obra no
devuelve las líneas base de otra.
"""

from __future__ import annotations

import inspect
import re
import uuid
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any, NamedTuple

import pytest
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from cimenta.presupuesto.api.esquemas import Unidad
from cimenta.presupuesto.dominio.catalogo import UNIDADES_ADMITIDAS
from cimenta.presupuesto.infraestructura import repositorio_linea_base
from herramientas.soporte_tkt017 import preparacion_dos_niveles
from herramientas.soporte_tkt017_api import (
    CABECERA_CORRELACION,
    NOMBRE_DEL_DIRECTOR,
    OTRO_TOKEN_CSRF,
    RAIZ,
    ROLES_DE_LECTURA,
    ROLES_SIN_LECTURA,
    TOKEN_CSRF,
    VENTA_POR_TIPO,
    Sesion,
    abrir_sesion,  # noqa: F401
    base,  # noqa: F401
    borrador,
    componentes_duplicados,
    construir_aplicacion,
    contexto,  # noqa: F401
    diferencias_de_forma,
    entorno,  # noqa: F401
    esquema_de_respuesta_200,
    exigir_denegacion,
    exigir_error,
    forma_de,
    forma_de_componente,
    leer,
    leer_con_par_csrf,
    llamadas,
    parametros_de,
    publicado,
    rutas_de,
    tipo_esperado,
    tipos_de_partida,
    validar_contra,
)
from herramientas.soporte_tkt017_entorno import (
    MOTIVO_DE_CONGELADO,
    Base,
    Contexto,
    Entorno,
    congelar,
)

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta.
    from conftest import DatosPresupuesto, RelojDePrueba
    from fastapi.routing import APIRoute
    from fastapi.testclient import TestClient

MENSAJE_LINEA_BASE_NO_EXISTE = "La línea base no existe."
MENSAJE_OBRA_NO_EXISTE = "La obra no existe."
MENSAJE_ROL_INSUFICIENTE = "Tu rol no permite esta operación."
MENSAJE_SIN_SESION = "No hay una sesión iniciada."
MENSAJE_UN_CAMPO_INVALIDO = "La petición tiene 1 campo inválido."
MENSAJE_FUERA_DE_RANGO = "El valor está fuera del rango permitido."
MENSAJE_FORMATO = "El valor no tiene el formato esperado."


# El libro de `preparacion_dos_niveles` (`VENTA_POR_TIPO` es su desglose por tipo).
IMPORTE_DEL_LIBRO = "63000.0000"
CODIGO_DEL_INSUMO = "PANEL YESO 1/2"
# Por tipo: 6 × 12.5 × 0.6734 = 50.5050 de panel a 85.5000 = 4318.1775; el total son los dos renglones.
IMPORTE_COSTO_POR_TIPO = "4318.1775"
IMPORTE_TOTAL_DEL_LIBRO = "8636.3550"
# Lo que ningún `403` ni ningún `401` debe dejar ver del libro.
CIFRAS_Y_NOMBRES_DEL_LIBRO = [
    "63000",
    "31500",
    "5250",
    "4318",
    "8636",
    "420.0000",
    "12.5000",
    "85.5000",
    "0.6734",
    "50.505",
    "620040",
    "Tablaroca",
    "PANEL YESO",
    "SOTANO",
    MOTIVO_DE_CONGELADO,
]
# Nivel, área y tipo en el orden `nivel.orden, area.nombre, partida.orden`: las áreas se ordenan por nombre
# (el libro las declara Z, M, A) y dentro del área PLAFON (orden 1) va antes que MUROS EXTERIORES (orden 2).
SECUENCIA_DEL_LIBRO = [
    (nivel, area, tipo)
    for nivel in ("SOTANO", "AZOTEA")
    for area in ("ZONA A", "ZONA M", "ZONA Z")
    for tipo in ("PLAFONES_Y_CAJILLOS", "MUROS")
]


class Lectura(NamedTuple):
    """Una de las cuatro operaciones de lectura del borrador."""

    operacion: str
    publicada: str
    parametro: str
    recurso: str
    mensaje_404: str

    def ruta(self, identificador: uuid.UUID | str) -> str:
        return self.publicada.replace("{" + self.parametro + "}", str(identificador))

    def ruta_de(self, obra_id: uuid.UUID, linea_base_id: uuid.UUID) -> str:
        return self.ruta(obra_id if self.parametro == "obra_id" else linea_base_id)


LECTURAS = [
    Lectura(
        "listar_lineas_base",
        "/api/v1/obras/{obra_id}/lineas-base",
        "obra_id",
        "obra",
        MENSAJE_OBRA_NO_EXISTE,
    ),
    Lectura(
        "obtener_linea_base",
        "/api/v1/lineas-base/{linea_base_id}",
        "linea_base_id",
        "linea_base",
        MENSAJE_LINEA_BASE_NO_EXISTE,
    ),
    Lectura(
        "listar_conceptos_linea_base",
        "/api/v1/lineas-base/{linea_base_id}/conceptos",
        "linea_base_id",
        "linea_base",
        MENSAJE_LINEA_BASE_NO_EXISTE,
    ),
    Lectura(
        "obtener_explosion_insumos",
        "/api/v1/lineas-base/{linea_base_id}/explosion",
        "linea_base_id",
        "linea_base",
        MENSAJE_LINEA_BASE_NO_EXISTE,
    ),
]
POR_LECTURA = [pytest.param(lectura, id=lectura.operacion) for lectura in LECTURAS]


def la_lectura(operacion: str) -> Lectura:
    return next(lectura for lectura in LECTURAS if lectura.operacion == operacion)


def ruta_de_linea_base(linea_base_id: uuid.UUID) -> str:
    return la_lectura("obtener_linea_base").ruta(linea_base_id)


def ruta_de_conceptos(linea_base_id: uuid.UUID) -> str:
    return la_lectura("listar_conceptos_linea_base").ruta(linea_base_id)


def ruta_de_explosion(linea_base_id: uuid.UUID) -> str:
    return la_lectura("obtener_explosion_insumos").ruta(linea_base_id)


def ruta_de_lineas_de_obra(obra_id: uuid.UUID) -> str:
    return la_lectura("listar_lineas_base").ruta(obra_id)


@pytest.fixture
def borrador_real(entorno: Entorno, contexto: Contexto) -> uuid.UUID:
    """La línea base `BORRADOR` que sale de confirmar el libro de 12 apariciones (la jerarquía real)."""
    entorno.importacion_id = entorno.importar(preparacion=preparacion_dos_niveles())
    return entorno.confirmar(contexto).linea_base_id


class Congelada(NamedTuple):
    linea_base_id: uuid.UUID
    director: Sesion
    momento: datetime


@pytest.fixture
def congelada(
    borrador_real: uuid.UUID,
    contexto: Contexto,
    abrir_sesion: Callable[..., Sesion],
    reloj_de_prueba: RelojDePrueba,
) -> Congelada:
    """El libro real congelado por un director distinto del que confirmó, diez minutos después."""
    director = abrir_sesion(("DIRECTOR_PROYECTOS",), nombre=NOMBRE_DEL_DIRECTOR)
    reloj_de_prueba.avanzar(timedelta(minutes=10))
    congelar(contexto(), borrador_real, usuario_id=director.usuario_id)
    return Congelada(borrador_real, director, reloj_de_prueba.ahora)


# --------------------------------------------------------------------------- lo esperado del libro real


def _por_tipo_esperado(base: Base, importes: Mapping[str, str]) -> list[dict[str, Any]]:
    return [
        {
            "tipo_partida": {"id": str(identificador), "clave": clave, "nombre": nombre},
            "importe_venta": importes[clave],
        }
        for identificador, clave, nombre in tipos_de_partida(base)
    ]


def _linea_congelada_esperada(
    base: Base,
    entorno: Entorno,
    congelada: Congelada,
    importes: Mapping[str, str] = VENTA_POR_TIPO,
) -> dict[str, Any]:
    """La `LineaBase` del libro real congelado, sin `congelada_en` (que se compara aparte, con zona)."""
    return {
        "id": str(congelada.linea_base_id),
        "obra_id": str(entorno.obra_id),
        "version": 1,
        "estado": "CONGELADA",
        "importe_venta": IMPORTE_DEL_LIBRO,
        "congelada_por": {"id": str(congelada.director.usuario_id), "nombre": NOMBRE_DEL_DIRECTOR},
        "motivo": MOTIVO_DE_CONGELADO,
        "por_tipo_partida": _por_tipo_esperado(base, importes),
    }


def _exigir_linea_congelada(
    cuerpo: dict[str, Any],
    base: Base,
    entorno: Entorno,
    congelada: Congelada,
    importes: Mapping[str, str] = VENTA_POR_TIPO,
) -> None:
    """La forma exacta de `LineaBase` del borrador para el libro real congelado."""
    assert set(cuerpo) == {
        "id",
        "obra_id",
        "version",
        "estado",
        "importe_venta",
        "congelada_en",
        "congelada_por",
        "motivo",
        "por_tipo_partida",
    }
    assert isinstance(cuerpo["congelada_en"], str)
    assert datetime.fromisoformat(cuerpo["congelada_en"]) == congelada.momento
    sin_fecha = {clave: valor for clave, valor in cuerpo.items() if clave != "congelada_en"}
    assert sin_fecha == _linea_congelada_esperada(base, entorno, congelada, importes)
    validar_contra("LineaBase", cuerpo)


def _renglon_esperado(base: Base, clave: str) -> dict[str, Any]:
    insumos = base.filas(
        "SELECT id, codigo, descripcion, unidad FROM insumo WHERE codigo = %s", CODIGO_DEL_INSUMO
    )
    assert len(insumos) == 1
    identificador, codigo, descripcion, unidad = insumos[0]
    return {
        "tipo_partida": tipo_esperado(base, clave),
        "insumo": {
            "id": str(identificador),
            "codigo": codigo,
            "descripcion": descripcion,
            "unidad": unidad,
        },
        "cantidad_presupuestada": "50.5050",
        "rendimiento_congelado": "0.673400",
        "costo_unitario": "85.5000",
        "importe_costo": IMPORTE_COSTO_POR_TIPO,
    }


def _renglones_por_clave(cuerpo: dict[str, Any]) -> list[dict[str, Any]]:
    """Los renglones ordenados por clave de tipo: el borrador no fija el orden de la explosión."""
    return sorted(cuerpo["renglones"], key=lambda renglon: str(renglon["tipo_partida"]["clave"]))


def _obtener(
    cliente: TestClient, ruta: str, sesion: Sesion, esquema: str, **consulta: object
) -> Any:
    """Una lectura que debe responder `200` y cuyo cuerpo cumple el esquema del borrador."""
    respuesta = leer(cliente, ruta, sesion.sesion_id, **consulta)
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.headers["content-type"].startswith("application/json")
    cuerpo = respuesta.json()
    validar_contra(esquema, cuerpo)
    return cuerpo


def _bitacora_sin_denegaciones(base: Base) -> list[tuple[Any, ...]]:
    return base.filas("SELECT * FROM bitacora WHERE accion <> 'DENEGAR' ORDER BY id")


# --------------------------------------------------------------------------- TC-B13 · CA-B8 esc. 1


@pytest.mark.parametrize("rol", ROLES_DE_LECTURA)
def test_hdu001_esc14_lecturas_de_la_linea_base(
    rol: str,
    entorno: Entorno,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    congelada: Congelada,
) -> None:
    """HDU-001 esc. 14 · TC-B13 · CA-B8 esc. 1 · RN-01 — los tres roles leen las cuatro lecturas, con la forma del borrador.

    Sin cabecera ni cookie CSRF: son `GET`. La línea base congelada sale con quién la congeló, las cuatro
    filas de `por_tipo_partida` ordenadas por `id`, los conceptos en la primera página por omisión (1 de 50)
    y la explosión con sus dos renglones; ninguna lectura escribe en la bitácora.
    """
    lector = abrir_sesion((rol,))
    asientos_antes = base.filas("SELECT count(*) FROM bitacora")

    linea = _obtener(cliente, ruta_de_linea_base(congelada.linea_base_id), lector, "LineaBase")
    lineas = _obtener_lista_de_lineas(cliente, ruta_de_lineas_de_obra(entorno.obra_id), lector)
    conceptos = _obtener(
        cliente, ruta_de_conceptos(congelada.linea_base_id), lector, "ListaConceptosLineaBase"
    )
    explosion = _obtener(
        cliente, ruta_de_explosion(congelada.linea_base_id), lector, "ExplosionInsumos"
    )

    _exigir_linea_congelada(linea, base, entorno, congelada)
    assert lineas == [linea]
    assert set(conceptos) == {"elementos", "paginacion"}
    assert conceptos["paginacion"] == {"pagina": 1, "tamano_pagina": 50, "total": 12}
    assert len(conceptos["elementos"]) == 12
    assert set(explosion) == {"linea_base_id", "renglones", "importe_total"}
    assert explosion["linea_base_id"] == str(congelada.linea_base_id)
    assert explosion["importe_total"] == IMPORTE_TOTAL_DEL_LIBRO
    assert len(explosion["renglones"]) == 2
    assert base.filas("SELECT count(*) FROM bitacora") == asientos_antes, (
        "Una lectura no escribe en la bitácora"
    )


def _obtener_lista_de_lineas(cliente: TestClient, ruta: str, sesion: Sesion) -> list[Any]:
    """`listar_lineas_base`: un arreglo de `LineaBase`, cada elemento válido contra el borrador."""
    respuesta = leer(cliente, ruta, sesion.sesion_id)
    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.headers["content-type"].startswith("application/json")
    cuerpo = respuesta.json()
    assert isinstance(cuerpo, list)
    for elemento in cuerpo:
        validar_contra("LineaBase", elemento)
    return cuerpo


def test_hdu001_esc14_quien_suma_un_rol_de_lectura_lee(
    congelada: Congelada,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
) -> None:
    """HDU-001 esc. 14 · TC-B13 · CA-B8 — el permiso es la unión de los roles: `RESIDENTE` más `COMPRAS` lee la explosión."""
    lector = abrir_sesion(("RESIDENTE", "COMPRAS"))

    explosion = _obtener(
        cliente, ruta_de_explosion(congelada.linea_base_id), lector, "ExplosionInsumos"
    )

    assert explosion["importe_total"] == IMPORTE_TOTAL_DEL_LIBRO


def test_hdu001_esc14_listar_lineas_base_trae_las_versiones_de_la_obra_la_mas_reciente_primero(
    datos_presupuesto: DatosPresupuesto,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
) -> None:
    """HDU-001 esc. 14 · TC-B13 · CA-B8 · RN-01 — versión descendente; la línea base de otra obra no aparece.

    La obra tiene la versión 1 `SUPERSEDIDA`, la 2 `CONGELADA` y la 3 `BORRADOR`; otra obra tiene la suya.
    Las congeladas traen quién y cuándo; el borrador, nulos. Una obra sin líneas base responde `[]`.
    """
    datos = datos_presupuesto
    obra = datos.obra(codigo="AP-101-26")
    otra_obra = datos.obra(codigo="AP-102-26")
    sin_lineas = datos.obra(codigo="AP-103-26")
    v1 = datos.linea_base(estado="SUPERSEDIDA", obra_id=obra, version=1)
    v2 = datos.linea_base(estado="CONGELADA", obra_id=obra, version=2)
    v3 = datos.linea_base(estado="BORRADOR", obra_id=obra, version=3)
    ajena = datos.linea_base(estado="BORRADOR", obra_id=otra_obra, version=1)
    lector = abrir_sesion(("COMPRAS",))

    lineas = _obtener_lista_de_lineas(cliente, ruta_de_lineas_de_obra(obra), lector)
    de_la_otra = _obtener_lista_de_lineas(cliente, ruta_de_lineas_de_obra(otra_obra), lector)
    vacia = _obtener_lista_de_lineas(cliente, ruta_de_lineas_de_obra(sin_lineas), lector)

    assert [(linea["id"], linea["version"], linea["estado"]) for linea in lineas] == [
        (str(v3), 3, "BORRADOR"),
        (str(v2), 2, "CONGELADA"),
        (str(v1), 1, "SUPERSEDIDA"),
    ]
    assert {linea["obra_id"] for linea in lineas} == {str(obra)}
    assert [linea["id"] for linea in de_la_otra] == [str(ajena)]
    assert vacia == []
    assert all(len(linea["por_tipo_partida"]) == 4 for linea in lineas)
    congelada_v2 = lineas[1]
    quien = base.filas("SELECT congelada_por_id FROM linea_base WHERE id = %s", v2)[0][0]
    assert congelada_v2["importe_venta"] == "1000000.0000"
    assert congelada_v2["congelada_por"] == {"id": str(quien), "nombre": "Usuario de prueba"}
    assert datetime.fromisoformat(congelada_v2["congelada_en"]) == datetime(
        2026, 10, 21, 12, 0, tzinfo=UTC
    )
    assert lineas[0].get("congelada_en") is None
    assert lineas[0].get("congelada_por") is None


def test_hdu001_esc14_conceptos_en_el_orden_del_borrador_con_sus_cifras_como_cadena(
    entorno: Entorno,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    congelada: Congelada,
) -> None:
    """HDU-001 esc. 14 · TC-B13 · CA-B8 esc. 1 — 12 conceptos por `nivel.orden`, `area.nombre` y `partida.orden`, cifras con su escala.

    El `id` es el de la copia (`linea_base_concepto`). Cantidad con cuatro decimales, precio con cuatro e
    importe con cuatro, todo cadena. `nivel` y `area` son los nombres y `tipo_partida` el resumen del tipo.
    """
    lector = abrir_sesion(("DIRECCION_GENERAL",))

    cuerpo = _obtener(
        cliente, ruta_de_conceptos(congelada.linea_base_id), lector, "ListaConceptosLineaBase"
    )

    elementos = cuerpo["elementos"]
    assert [(e["nivel"], e["area"], e["tipo_partida"]["clave"]) for e in elementos] == (
        SECUENCIA_DEL_LIBRO
    )
    assert all(
        set(e)
        == {
            "id",
            "codigo",
            "descripcion",
            "unidad",
            "cantidad",
            "precio_unitario",
            "importe",
            "nivel",
            "area",
            "tipo_partida",
        }
        for e in elementos
    )
    assert {
        (
            e["codigo"],
            e["descripcion"],
            e["unidad"],
            e["cantidad"],
            e["precio_unitario"],
            e["importe"],
        )
        for e in elementos
    } == {("620040-A", "Tablaroca", "M2", "12.5000", "420.0000", "5250.0000")}
    assert all(
        e["tipo_partida"] == tipo_esperado(base, e["tipo_partida"]["clave"]) for e in elementos
    )
    copias = {
        str(fila[0])
        for fila in base.filas(
            "SELECT id FROM linea_base_concepto WHERE linea_base_id = %s", congelada.linea_base_id
        )
    }
    assert {e["id"] for e in elementos} == copias
    assert len(copias) == 12


@pytest.mark.parametrize(
    ("clave", "cuantos"),
    [
        pytest.param("MUROS", 6, id="muros"),
        pytest.param("PLAFONES_Y_CAJILLOS", 6, id="plafones"),
        pytest.param("ENCHAPES", 0, id="enchapes_sin_conceptos"),
    ],
)
def test_hdu001_esc14_conceptos_filtran_por_tipo_de_partida(
    clave: str,
    cuantos: int,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    congelada: Congelada,
) -> None:
    """HDU-001 esc. 14 · TC-B13 · CA-B8 esc. 1 — `tipo_partida_id` deja solo los conceptos de ese tipo y el `total` los cuenta."""
    lector = abrir_sesion(("COMPRAS",))
    tipo = tipo_esperado(base, clave)

    cuerpo = _obtener(
        cliente,
        ruta_de_conceptos(congelada.linea_base_id),
        lector,
        "ListaConceptosLineaBase",
        tipo_partida_id=tipo["id"],
    )

    assert cuerpo["paginacion"] == {"pagina": 1, "tamano_pagina": 50, "total": cuantos}
    assert len(cuerpo["elementos"]) == cuantos
    assert {e["tipo_partida"]["clave"] for e in cuerpo["elementos"]} <= {clave}


@pytest.mark.parametrize(
    ("nivel", "cuantos"),
    [
        pytest.param("SOTANO", 6, id="sotano"),
        pytest.param("AZOTEA", 6, id="azotea"),
        pytest.param("NIVEL-QUE-NO-EXISTE", 0, id="inexistente"),
        pytest.param("sotano", 0, id="distingue_mayusculas"),
        pytest.param("SOTA", 0, id="no_es_prefijo"),
    ],
)
def test_hdu001_esc14_conceptos_filtran_por_nivel(
    nivel: str,
    cuantos: int,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    congelada: Congelada,
) -> None:
    """HDU-001 esc. 14 · TC-B13 · CA-B8 esc. 1 — `nivel` es igualdad exacta, sensible a mayúsculas, con el nombre del nivel.

    `sotano` (otra caja) y `SOTA` (un prefijo) no coinciden con `SOTANO`. Protegen los mutantes que
    cambian la igualdad por `ILIKE` o por una búsqueda de subcadena sobre `nivel.nombre`.
    """
    lector = abrir_sesion(("COMPRAS",))

    cuerpo = _obtener(
        cliente,
        ruta_de_conceptos(congelada.linea_base_id),
        lector,
        "ListaConceptosLineaBase",
        nivel=nivel,
    )

    assert cuerpo["paginacion"]["total"] == cuantos
    assert {e["nivel"] for e in cuerpo["elementos"]} <= {nivel}
    assert len(cuerpo["elementos"]) == cuantos


def test_hdu001_esc14_conceptos_con_nivel_vacio_no_coincide_con_ningun_nivel(
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    congelada: Congelada,
) -> None:
    """HDU-001 esc. 14 · TC-B13 · CA-B8 — `nivel=` (cadena vacía) es igualdad con un nombre vacío: `200` con cero conceptos.

    Decisión de la persona dueña: el filtro vacío no se ignora. Ningún nivel se llama «», así que la
    página sale vacía y el `total` es 0 (no los 12 de la línea base).
    """
    lector = abrir_sesion(("COMPRAS",))

    cuerpo = _obtener(
        cliente,
        ruta_de_conceptos(congelada.linea_base_id),
        lector,
        "ListaConceptosLineaBase",
        nivel="",
    )

    assert cuerpo == {
        "elementos": [],
        "paginacion": {"pagina": 1, "tamano_pagina": 50, "total": 0},
    }


def test_hdu001_esc14_conceptos_con_texto_vacio_devuelve_todos(
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    congelada: Congelada,
) -> None:
    """HDU-001 esc. 14 · TC-B13 · CA-B8 — `q=` (cadena vacía) es una subcadena que todo texto contiene: `200` con los 12 conceptos."""
    lector = abrir_sesion(("COMPRAS",))

    cuerpo = _obtener(
        cliente,
        ruta_de_conceptos(congelada.linea_base_id),
        lector,
        "ListaConceptosLineaBase",
        q="",
    )

    assert cuerpo["paginacion"] == {"pagina": 1, "tamano_pagina": 50, "total": 12}
    assert [(e["nivel"], e["area"], e["tipo_partida"]["clave"]) for e in cuerpo["elementos"]] == (
        SECUENCIA_DEL_LIBRO
    )


def test_hdu001_esc14_conceptos_combinan_tipo_y_nivel(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    congelada: Congelada,
) -> None:
    """HDU-001 esc. 14 · TC-B13 · CA-B8 esc. 1 — los filtros se combinan con «y»: MUROS en AZOTEA son tres áreas."""
    lector = abrir_sesion(("COMPRAS",))

    cuerpo = _obtener(
        cliente,
        ruta_de_conceptos(congelada.linea_base_id),
        lector,
        "ListaConceptosLineaBase",
        tipo_partida_id=tipo_esperado(base, "MUROS")["id"],
        nivel="AZOTEA",
    )

    assert [(e["nivel"], e["area"], e["tipo_partida"]["clave"]) for e in cuerpo["elementos"]] == [
        ("AZOTEA", "ZONA A", "MUROS"),
        ("AZOTEA", "ZONA M", "MUROS"),
        ("AZOTEA", "ZONA Z", "MUROS"),
    ]
    assert cuerpo["paginacion"]["total"] == 3


@pytest.mark.parametrize(
    ("q", "cuantos"),
    [
        pytest.param("620040", 12, id="por_codigo"),
        pytest.param("tablaroca", 12, id="por_descripcion_sin_distinguir_mayusculas"),
        pytest.param("TABLA", 12, id="por_parte_de_la_descripcion"),
        pytest.param("SOTANO", 0, id="no_busca_en_el_nivel"),
        pytest.param("no-existe-en-ningun-concepto", 0, id="sin_coincidencias"),
    ],
)
def test_hdu001_esc14_conceptos_filtran_por_texto(
    q: str,
    cuantos: int,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    congelada: Congelada,
) -> None:
    """HDU-001 esc. 14 · TC-B13 · CA-B8 esc. 1 — `q` busca por parte del código o de la descripción, sin distinguir mayúsculas."""
    lector = abrir_sesion(("COMPRAS",))

    cuerpo = _obtener(
        cliente,
        ruta_de_conceptos(congelada.linea_base_id),
        lector,
        "ListaConceptosLineaBase",
        q=q,
    )

    assert cuerpo["paginacion"]["total"] == cuantos
    assert len(cuerpo["elementos"]) == cuantos


def test_hdu001_esc14_conceptos_paginan_con_el_total_del_filtro(
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    congelada: Congelada,
) -> None:
    """HDU-001 esc. 14 · TC-B13 · CA-B8 esc. 1 — páginas de 5: 5, 5, 2 y vacía; el `total` es 12 en todas y el orden se continúa.

    Las páginas concatenadas son la lista completa (`tamano_pagina=200`, el máximo), sin repetir ni
    saltar ninguna fila. Con un filtro, el `total` es el de las filas filtradas y no el de la línea base.
    """
    lector = abrir_sesion(("COMPRAS",))
    ruta = ruta_de_conceptos(congelada.linea_base_id)

    completa = _obtener(cliente, ruta, lector, "ListaConceptosLineaBase", tamano_pagina=200)
    paginas = [
        _obtener(cliente, ruta, lector, "ListaConceptosLineaBase", pagina=n, tamano_pagina=5)
        for n in (1, 2, 3, 4)
    ]
    filtrada = _obtener(
        cliente, ruta, lector, "ListaConceptosLineaBase", nivel="SOTANO", pagina=2, tamano_pagina=4
    )

    assert completa["paginacion"] == {"pagina": 1, "tamano_pagina": 200, "total": 12}
    assert [len(p["elementos"]) for p in paginas] == [5, 5, 2, 0]
    assert [p["paginacion"] for p in paginas] == [
        {"pagina": n, "tamano_pagina": 5, "total": 12} for n in (1, 2, 3, 4)
    ]
    assert [e["id"] for p in paginas for e in p["elementos"]] == [
        e["id"] for e in completa["elementos"]
    ]
    assert filtrada["paginacion"] == {"pagina": 2, "tamano_pagina": 4, "total": 6}
    assert len(filtrada["elementos"]) == 2


@pytest.mark.parametrize(
    ("pagina", "tamano_pagina"),
    [
        pytest.param(10**6, 200, id="un_millon"),
        pytest.param(2**62, 200, id="dos_a_la_62"),
        pytest.param(2**63, 200, id="dos_a_la_63"),
        pytest.param(10**30, 200, id="diez_a_la_30"),
        pytest.param(2**63, None, id="dos_a_la_63_con_tamano_por_omision"),
    ],
)
def test_tkt017_cab08_conceptos_con_pagina_enorme_responde_pagina_vacia(
    pagina: int,
    tamano_pagina: int | None,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    congelada: Congelada,
) -> None:
    """TC-B13 · CA-B8 — una `pagina` más allá del final, por grande que sea, es `200` con la página vacía y el `total` de la línea base.

    Decisión de la persona dueña (2026-11-10): el borrador no fija un
    tope de `pagina`, y el tope lo decide TKT-027. El desplazamiento
    `(pagina - 1) * tamano_pagina` desborda el `bigint` de PostgreSQL desde `2**63 / 200`: sin proteger
    esa cuenta la consulta acaba en `500`. Aquí la línea base congelada tiene 12 conceptos, y la
    paginación devuelve la `pagina` y el `tamano_pagina` pedidos. Una lectura no escribe en la bitácora.
    """
    lector = abrir_sesion(("COMPRAS",))
    asientos_antes = base.filas("SELECT count(*) FROM bitacora")
    consulta: dict[str, object] = {"pagina": pagina}
    if tamano_pagina is not None:
        consulta["tamano_pagina"] = tamano_pagina

    cuerpo = _obtener(
        cliente,
        ruta_de_conceptos(congelada.linea_base_id),
        lector,
        "ListaConceptosLineaBase",
        **consulta,
    )

    assert cuerpo == {
        "elementos": [],
        "paginacion": {
            "pagina": pagina,
            "tamano_pagina": 50 if tamano_pagina is None else tamano_pagina,
            "total": 12,
        },
    }
    assert base.filas("SELECT count(*) FROM bitacora") == asientos_antes


# Línea base sembrada a mano: (clave del tipo, código del concepto, descripción). Los códigos y las
# descripciones llevan los caracteres que `LIKE` comodina (`%`, `_`) y el que `autoescape` usa para escapar (`/`).
CONCEPTOS_A_MANO = [
    ("MUROS", "620001", "Muro falso 100% resistente"),
    ("PLAFONES_Y_CAJILLOS", "AB_01", "Plafón liso"),
    ("ENCHAPES", "ab-03", "Panel 1/2 pulgada"),
]
# Insumo, tipo, cantidad (4), rendimiento (6), costo (4) e importe (4) de los dos renglones sembrados.
RENGLONES_A_MANO = [
    ("INS-A", "MUROS", "3.3333", "0.333333", "1.2345", "4.1149"),
    ("INS-B", "ENCHAPES", "10.0000", "2.500000", "0.0100", "0.1000"),
]


class AMano(NamedTuple):
    linea_base_id: uuid.UUID
    obra_id: uuid.UUID


@pytest.fixture
def congelada_a_mano(datos_presupuesto: DatosPresupuesto) -> AMano:
    """Una línea base `CONGELADA` con tres conceptos de texto a medida y dos renglones de explosión.

    Las copias y la explosión se insertan con la línea base en `BORRADOR` (el disparador del invariante 14
    solo lo admite ahí) y después se congela con `UPDATE`, como el congelado real.
    """
    datos = datos_presupuesto
    obra = datos.obra(codigo="AP-099-26")
    tipos = {
        clave: datos.tipo_partida(clave=clave)
        for clave in ("MUROS", "PLAFONES_Y_CAJILLOS", "ENCHAPES", "GENERALES")
    }
    linea_base = datos.linea_base(
        estado="BORRADOR", obra_id=obra, version=1, importe_venta=Decimal("300.0000")
    )
    area = datos.area(
        nivel_id=datos.nivel(obra_id=obra, nombre="NIVEL 1", orden=1), nombre="COCINA"
    )
    for orden, (clave, codigo, descripcion) in enumerate(CONCEPTOS_A_MANO, start=1):
        aparicion = datos.partida_concepto(
            concepto_id=datos.concepto(obra_id=obra, codigo=codigo, descripcion=descripcion),
            partida_id=datos.partida(area_id=area, tipo_partida_id=tipos[clave], orden=orden),
            cantidad=Decimal("2.0000"),
            precio_unitario=Decimal("50.0000"),
            importe=Decimal("100.0000"),
        )
        datos.copia_concepto(
            linea_base_id=linea_base,
            partida_concepto_id=aparicion,
            codigo=codigo,
            cantidad=Decimal("2.0000"),
            precio_unitario=Decimal("50.0000"),
            importe=Decimal("100.0000"),
        )
    for codigo_insumo, clave, cantidad, rendimiento, costo, importe in RENGLONES_A_MANO:
        datos.renglon_explosion(
            linea_base_id=linea_base,
            tipo_partida_id=tipos[clave],
            insumo_id=datos.insumo(codigo=codigo_insumo, descripcion=f"Insumo {codigo_insumo}"),
            cantidad_presupuestada=Decimal(cantidad),
            rendimiento_congelado=Decimal(rendimiento),
            costo_unitario=Decimal(costo),
            importe_venta=Decimal(importe),
        )
    datos.congelar(linea_base)
    return AMano(linea_base, obra)


@pytest.mark.parametrize(
    ("q", "codigos"),
    [
        pytest.param("%", ["620001"], id="porcentaje_es_literal"),
        pytest.param("100%", ["620001"], id="porcentaje_dentro_de_un_texto"),
        pytest.param("_", ["AB_01"], id="guion_bajo_es_literal"),
        pytest.param("6_0001", [], id="guion_bajo_no_comodina_un_caracter"),
        pytest.param("62%01", [], id="porcentaje_no_comodina_una_cadena"),
        pytest.param("1/2", ["ab-03"], id="diagonal_es_literal"),
        pytest.param("ab", ["AB_01", "ab-03"], id="sin_distinguir_mayusculas"),
    ],
)
def test_hdu001_esc14_conceptos_q_con_caracteres_de_comodin_no_comodina(
    q: str,
    codigos: list[str],
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    congelada_a_mano: AMano,
) -> None:
    """HDU-001 esc. 14 · TC-B13 · CA-B8 esc. 1 — `q` con `%`, `_` o `/` busca ese carácter, no un comodín (`autoescape=True`).

    Con `%` o `_` sin escapar, el filtro devolvería los tres conceptos. `6_0001` y `62%01` no están en
    ningún código ni descripción, así que solo un comodín los haría coincidir con `620001`.
    """
    lector = abrir_sesion(("COMPRAS",))

    cuerpo = _obtener(
        cliente,
        ruta_de_conceptos(congelada_a_mano.linea_base_id),
        lector,
        "ListaConceptosLineaBase",
        q=q,
    )

    assert sorted(e["codigo"] for e in cuerpo["elementos"]) == sorted(codigos)
    assert cuerpo["paginacion"]["total"] == len(codigos)


def test_hdu001_esc14_explosion_forma_y_cifras_como_cadena(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    congelada: Congelada,
) -> None:
    """HDU-001 esc. 14 · TC-B13 · CA-B8 · CA-B9 · RN-24 — dos renglones con `importe_costo` (no `importe_venta`) y cifras con su escala.

    Cantidad con cuatro decimales, rendimiento congelado con seis, costo unitario e `importe_costo` con
    cuatro. `importe_total` es la suma de los renglones devueltos: 2 × 4318.1775.
    """
    lector = abrir_sesion(("DIRECCION_GENERAL",))

    cuerpo = _obtener(
        cliente, ruta_de_explosion(congelada.linea_base_id), lector, "ExplosionInsumos"
    )

    assert cuerpo["linea_base_id"] == str(congelada.linea_base_id)
    assert cuerpo["importe_total"] == IMPORTE_TOTAL_DEL_LIBRO
    assert _renglones_por_clave(cuerpo) == [
        _renglon_esperado(base, "MUROS"),
        _renglon_esperado(base, "PLAFONES_Y_CAJILLOS"),
    ]
    assert all("importe_venta" not in renglon for renglon in cuerpo["renglones"])


@pytest.mark.parametrize(
    ("clave", "renglones", "importe_total"),
    [
        pytest.param("MUROS", 1, IMPORTE_COSTO_POR_TIPO, id="muros"),
        pytest.param("PLAFONES_Y_CAJILLOS", 1, IMPORTE_COSTO_POR_TIPO, id="plafones"),
        pytest.param("ENCHAPES", 0, "0.0000", id="enchapes_sin_renglones"),
    ],
)
def test_hdu001_esc14_explosion_filtra_por_tipo_y_suma_lo_devuelto(
    clave: str,
    renglones: int,
    importe_total: str,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    congelada: Congelada,
) -> None:
    """HDU-001 esc. 14 · TC-B13 · CA-B8 — con `tipo_partida_id`, solo los renglones de ese tipo y `importe_total` de los devueltos."""
    lector = abrir_sesion(("COMPRAS",))

    cuerpo = _obtener(
        cliente,
        ruta_de_explosion(congelada.linea_base_id),
        lector,
        "ExplosionInsumos",
        tipo_partida_id=tipo_esperado(base, clave)["id"],
    )

    assert len(cuerpo["renglones"]) == renglones
    assert {r["tipo_partida"]["clave"] for r in cuerpo["renglones"]} <= {clave}
    assert cuerpo["importe_total"] == importe_total


def test_hdu001_esc14_explosion_con_escalas_distintas_suma_sin_redondear(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    congelada_a_mano: AMano,
) -> None:
    """HDU-001 esc. 14 · TC-B13 · CA-B8 · RN-24 — cifras sembradas a medida: `importe_total` es 4.1149 + 0.1000 = 4.2149 y cada cifra conserva su escala.

    Rendimientos `0.333333` y `2.500000` (seis decimales), cantidad `10.0000` y costo `0.0100` (cuatro): ninguna
    se recorta ni se alarga. Con el filtro, `importe_total` es el del tipo y no el de la línea base completa.
    """
    lector = abrir_sesion(("COMPRAS",))
    ruta = ruta_de_explosion(congelada_a_mano.linea_base_id)

    todos = _obtener(cliente, ruta, lector, "ExplosionInsumos")
    solo_enchapes = _obtener(
        cliente,
        ruta,
        lector,
        "ExplosionInsumos",
        tipo_partida_id=tipo_esperado(base, "ENCHAPES")["id"],
    )

    assert todos["importe_total"] == "4.2149"
    assert [
        (
            r["tipo_partida"]["clave"],
            r["insumo"]["codigo"],
            r["cantidad_presupuestada"],
            r["rendimiento_congelado"],
            r["costo_unitario"],
            r["importe_costo"],
        )
        for r in _renglones_por_clave(todos)
    ] == [
        ("ENCHAPES", "INS-B", "10.0000", "2.500000", "0.0100", "0.1000"),
        ("MUROS", "INS-A", "3.3333", "0.333333", "1.2345", "4.1149"),
    ]
    assert solo_enchapes["importe_total"] == "0.1000"
    assert [r["insumo"]["codigo"] for r in solo_enchapes["renglones"]] == ["INS-B"]


# Tres tipos con tres insumos cada uno. Los códigos se reparten en rotación entre los tipos (A, D, G / B, E, H /
# C, F, I), de modo que ordenar solo por código mezcla los tipos y ordenar solo por tipo deja los códigos como
# se insertaron.
CODIGOS_DE_INSUMO_POR_TIPO = {
    "MUROS": ("ORD-A1", "ORD-D1", "ORD-G1"),
    "PLAFONES_Y_CAJILLOS": ("ORD-B1", "ORD-E1", "ORD-H1"),
    "ENCHAPES": ("ORD-C1", "ORD-F1", "ORD-I1"),
}


class ConInsumosDesordenados(NamedTuple):
    linea_base_id: uuid.UUID
    sembrados: list[
        tuple[uuid.UUID, str]
    ]  # (tipo_partida.id, insumo.codigo) en el orden en que se insertaron


@pytest.fixture
def congelada_con_insumos_desordenados(
    datos_presupuesto: DatosPresupuesto,
) -> ConInsumosDesordenados:
    """Una línea base `CONGELADA` con nueve renglones, insertados en orden de código descendente dentro de cada tipo.

    El orden de inserción (y con él el `id` del renglón) es el contrario al de código dentro de cada tipo, así que
    ni el orden físico ni el `id` producen el orden que la lectura promete.
    """
    datos = datos_presupuesto
    obra = datos.obra(codigo="AP-098-26")
    linea_base = datos.linea_base(
        estado="BORRADOR", obra_id=obra, version=1, importe_venta=Decimal("0.0000")
    )
    tipos = {clave: datos.tipo_partida(clave=clave) for clave in CODIGOS_DE_INSUMO_POR_TIPO}
    sembrados: list[tuple[uuid.UUID, str]] = []
    for posicion in (2, 1, 0):
        for clave, codigos in CODIGOS_DE_INSUMO_POR_TIPO.items():
            codigo = codigos[posicion]
            datos.renglon_explosion(
                linea_base_id=linea_base,
                tipo_partida_id=tipos[clave],
                insumo_id=datos.insumo(codigo=codigo, descripcion=f"Insumo {codigo}"),
                cantidad_presupuestada=Decimal("1.0000"),
                rendimiento_congelado=Decimal("1.000000"),
                costo_unitario=Decimal("1.0000"),
                importe_venta=Decimal("1.0000"),
            )
            sembrados.append((tipos[clave], codigo))
    datos.congelar(linea_base)
    return ConInsumosDesordenados(linea_base, sembrados)


def test_tkt017_cab08_la_explosion_sale_ordenada_por_tipo_y_codigo_de_insumo(
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    congelada_con_insumos_desordenados: ConInsumosDesordenados,
) -> None:
    """TKT-017 · CA-B8 · M-B19 — los renglones salen por `tipo_partida.id` y, dentro de cada tipo, por `insumo.codigo`.

    Es el orden que fijó el diseño de b2 (el mismo orden por `id` que `por_tipo_partida`). Lo esperado se calcula
    con `sorted` sobre lo sembrado, no sobre la respuesta, y la respuesta no se reordena antes de compararla.
    Mutantes `M-B19`: invertir los tres criterios del `ORDER BY`, o invertir solo el código de insumo.
    """
    lector = abrir_sesion(("COMPRAS",))
    sembrados = congelada_con_insumos_desordenados.sembrados
    esperado = [
        (str(tipo_id), codigo)
        for tipo_id, codigo in sorted(sembrados, key=lambda par: (par[0], par[1]))
    ]
    # El libro tiene que distinguir los criterios: ni el orden de inserción ni el código solo dan lo esperado.
    assert esperado != [(str(tipo_id), codigo) for tipo_id, codigo in sembrados]
    assert esperado != [
        (str(tipo_id), codigo) for tipo_id, codigo in sorted(sembrados, key=lambda par: par[1])
    ]

    cuerpo = _obtener(
        cliente,
        ruta_de_explosion(congelada_con_insumos_desordenados.linea_base_id),
        lector,
        "ExplosionInsumos",
    )

    assert [
        (renglon["tipo_partida"]["id"], renglon["insumo"]["codigo"])
        for renglon in cuerpo["renglones"]
    ] == esperado


def test_hdu001_esc14_lecturas_de_una_congelada_ignoran_partida_concepto(
    entorno: Entorno,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    congelada: Congelada,
) -> None:
    """HDU-001 esc. 14 · TC-B13 · CA-B8 · M-B8 — tras congelar, cambiar `partida_concepto` no mueve ninguna lectura.

    El rol de aplicación sí puede modificar `partida_concepto`; la línea base congelada no puede enterarse.
    `por_tipo_partida` (de `obtener_linea_base` y de `listar_lineas_base`) sigue siendo la suma de las
    copias, y los doce conceptos conservan el importe de su copia. Mutante `M-B8`: `importes_venta_por_tipo`
    suma `partida_concepto` también cuando la línea base está `CONGELADA`.
    """
    lector = abrir_sesion(("COMPRAS",))
    base.ejecutar(
        "UPDATE partida_concepto SET importe = 999999.0000 WHERE id IN "
        "(SELECT pc.id FROM partida_concepto pc JOIN concepto c ON c.id = pc.concepto_id "
        "WHERE c.obra_id = %s)",
        entorno.obra_id,
    )
    assert base.filas("SELECT DISTINCT importe FROM partida_concepto") == [("999999.0000",)], (
        "El cambio de partida_concepto debe haberse aplicado, o la comprobación no demuestra nada"
    )

    linea = _obtener(cliente, ruta_de_linea_base(congelada.linea_base_id), lector, "LineaBase")
    lineas = _obtener_lista_de_lineas(cliente, ruta_de_lineas_de_obra(entorno.obra_id), lector)
    conceptos = _obtener(
        cliente,
        ruta_de_conceptos(congelada.linea_base_id),
        lector,
        "ListaConceptosLineaBase",
        tamano_pagina=200,
    )

    _exigir_linea_congelada(linea, base, entorno, congelada)
    assert lineas == [linea]
    assert [e["importe"] for e in conceptos["elementos"]] == ["5250.0000"] * 12


def test_hdu001_esc14_lecturas_de_un_borrador(
    entorno: Entorno,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    borrador_real: uuid.UUID,
) -> None:
    """HDU-001 esc. 14 · TC-B13 · CA-B8 · P-9 — un `BORRADOR` no tiene copias: conceptos y explosión vacíos, `por_tipo_partida` de `partida_concepto`.

    Sin congelar, `congelada_en`, `congelada_por` y `motivo` son nulos. `importe_total` de la explosión
    vacía es `0.0000`. Los importes por tipo salen de `partida_concepto` y se mueven con ella (a diferencia
    de una congelada): se fija en 1000.0000 cada aparición y cada tipo suma 6 000.0000.
    """
    lector = abrir_sesion(("COMPRAS",))

    antes = _obtener(cliente, ruta_de_linea_base(borrador_real), lector, "LineaBase")
    conceptos = _obtener(
        cliente, ruta_de_conceptos(borrador_real), lector, "ListaConceptosLineaBase"
    )
    explosion = _obtener(cliente, ruta_de_explosion(borrador_real), lector, "ExplosionInsumos")
    lineas = _obtener_lista_de_lineas(cliente, ruta_de_lineas_de_obra(entorno.obra_id), lector)
    base.ejecutar(
        "UPDATE partida_concepto SET importe = 1000.0000 WHERE id IN "
        "(SELECT pc.id FROM partida_concepto pc JOIN concepto c ON c.id = pc.concepto_id "
        "WHERE c.obra_id = %s)",
        entorno.obra_id,
    )
    despues = _obtener(cliente, ruta_de_linea_base(borrador_real), lector, "LineaBase")

    assert antes["id"] == str(borrador_real)
    assert (antes["version"], antes["estado"], antes["importe_venta"]) == (
        1,
        "BORRADOR",
        IMPORTE_DEL_LIBRO,
    )
    assert antes.get("congelada_en") is None
    assert antes.get("congelada_por") is None
    assert antes.get("motivo") is None
    assert antes["por_tipo_partida"] == _por_tipo_esperado(base, VENTA_POR_TIPO)
    assert conceptos == {
        "elementos": [],
        "paginacion": {"pagina": 1, "tamano_pagina": 50, "total": 0},
    }
    assert explosion == {
        "linea_base_id": str(borrador_real),
        "renglones": [],
        "importe_total": "0.0000",
    }
    assert [linea["id"] for linea in lineas] == [str(borrador_real)]
    assert despues["por_tipo_partida"] == _por_tipo_esperado(
        base,
        {
            "MUROS": "6000.0000",
            "PLAFONES_Y_CAJILLOS": "6000.0000",
            "ENCHAPES": "0.0000",
            "GENERALES": "0.0000",
        },
    )


# --------------------------------------------------------------------------- TC-B14 · CA-B8 esc. 2


@pytest.mark.parametrize("lectura", POR_LECTURA)
@pytest.mark.parametrize("rol", ROLES_SIN_LECTURA)
def test_tkt017_cab08_lecturas_sin_rol(
    lectura: Lectura,
    rol: str,
    entorno: Entorno,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    congelada: Congelada,
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """TC-B14 · CA-B8 esc. 2 · RN-04 — sin `DIRECCION_GENERAL`, `DIRECTOR_PROYECTOS` ni `COMPRAS`: `403` `ROL_INSUFICIENTE`, sin importes, con un `DENEGAR`.

    Cuerpo exacto (sin `detalle`), `roles_requeridos` en el orden de `x-roles` del borrador. Ni las cifras
    del libro, ni el motivo del congelado, ni los identificadores de la obra o de la línea base aparecen en
    la respuesta; el único asiento nuevo es el `DENEGAR` a nombre de quien llamó, con `GET`, la ruta y los roles.
    """
    operacion = next(
        op
        for elemento in borrador()["paths"].values()
        for op in elemento.values()
        if isinstance(op, dict) and op.get("operationId") == lectura.operacion
    )
    assert operacion["x-roles"] == ROLES_DE_LECTURA, (
        "El borrador debe fijar los tres roles de lectura"
    )
    usuario = abrir_sesion((rol,))
    antes = _bitacora_sin_denegaciones(base)
    ruta = lectura.ruta_de(entorno.obra_id, congelada.linea_base_id)

    respuesta = leer(cliente, ruta, usuario.sesion_id)

    exigir_error(
        respuesta,
        estado=403,
        esperado={
            "tipo": "PERMISO",
            "motivo": "ROL_INSUFICIENTE",
            "mensaje": MENSAJE_ROL_INSUFICIENTE,
            "roles_requeridos": ROLES_DE_LECTURA,
        },
        esquema="ErrorPermiso",
    )
    # El `correlacion_id` es un UUID aleatorio: puede contener «5250», «4318» u «8636» por azar (~0,9 % por
    # corrida). Se quita del texto antes de buscar las cifras del libro; el resto del cuerpo queda intacto.
    texto = respuesta.text.replace(respuesta.headers[CABECERA_CORRELACION], "")
    assert texto != respuesta.text, "La correlación debe aparecer en el cuerpo para poder quitarla"
    for cifra_o_nombre in [
        *CIFRAS_Y_NOMBRES_DEL_LIBRO,
        str(entorno.obra_id),
        str(congelada.linea_base_id),
    ]:
        assert cifra_o_nombre not in texto
    assert _bitacora_sin_denegaciones(base) == antes
    exigir_denegacion(
        base,
        usuario_id=usuario.usuario_id,
        ocurrido_en=reloj_de_prueba.ahora,
        metodo="GET",
        ruta=ruta,
        roles_requeridos=ROLES_DE_LECTURA,
    )


@pytest.mark.parametrize("lectura", POR_LECTURA)
def test_tkt017_cab08_el_rol_se_comprueba_antes_que_la_existencia(
    lectura: Lectura,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """TC-B14 · CA-B8 esc. 2 · conv-seguridad — quien no tiene rol recibe `403` aunque el recurso no exista: no se averigua qué existe.

    Un `404` para un residente sobre un identificador inexistente y un `403` sobre uno real le dirían qué
    obras y líneas base existen. El asiento `DENEGAR` queda igual.
    """
    usuario = abrir_sesion(("RESIDENTE",))
    ruta = lectura.ruta(uuid.uuid4())

    respuesta = leer(cliente, ruta, usuario.sesion_id)

    exigir_error(
        respuesta,
        estado=403,
        esperado={
            "tipo": "PERMISO",
            "motivo": "ROL_INSUFICIENTE",
            "mensaje": MENSAJE_ROL_INSUFICIENTE,
            "roles_requeridos": ROLES_DE_LECTURA,
        },
        esquema="ErrorPermiso",
    )
    exigir_denegacion(
        base,
        usuario_id=usuario.usuario_id,
        ocurrido_en=reloj_de_prueba.ahora,
        metodo="GET",
        ruta=ruta,
        roles_requeridos=ROLES_DE_LECTURA,
    )


@pytest.mark.parametrize("lectura", POR_LECTURA)
def test_tkt017_cab08_lecturas_de_lo_inexistente(
    lectura: Lectura,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
) -> None:
    """TC-B14 · CA-B8 esc. 2 — la obra o la línea base no existen: `404` `NO_ENCONTRADO` con su `recurso` y su mensaje, no la ruta.

    `listar_lineas_base` responde con recurso `obra`; las otras tres, con `linea_base`. Un enrutador sin la
    ruta respondería `404` con la ruta como recurso: por eso se compara el cuerpo completo. No se asienta nada.
    """
    lector = abrir_sesion(("COMPRAS",))
    asientos_antes = base.filas("SELECT count(*) FROM bitacora")

    respuesta = leer(cliente, lectura.ruta(uuid.uuid4()), lector.sesion_id)

    exigir_error(
        respuesta,
        estado=404,
        esperado={
            "tipo": "NO_ENCONTRADO",
            "mensaje": lectura.mensaje_404,
            "recurso": lectura.recurso,
        },
        esquema="ErrorNoEncontrado",
    )
    assert base.filas("SELECT count(*) FROM bitacora") == asientos_antes


@pytest.mark.parametrize("lectura", POR_LECTURA[1:])
def test_tkt017_cab08_el_id_de_una_obra_no_abre_una_linea_base(
    lectura: Lectura,
    entorno: Entorno,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    congelada: Congelada,
) -> None:
    """TC-B14 · CA-B8 esc. 2 — pasar el `id` de la obra donde va el de la línea base responde `404` `linea_base`, sin cifras."""
    lector = abrir_sesion(("COMPRAS",))

    respuesta = leer(cliente, lectura.ruta(entorno.obra_id), lector.sesion_id)

    exigir_error(
        respuesta,
        estado=404,
        esperado={
            "tipo": "NO_ENCONTRADO",
            "mensaje": MENSAJE_LINEA_BASE_NO_EXISTE,
            "recurso": "linea_base",
        },
        esquema="ErrorNoEncontrado",
    )


@pytest.mark.parametrize("sesion", ["sin_cookie", "sesion_inexistente"])
@pytest.mark.parametrize("lectura", POR_LECTURA)
def test_tkt017_cab08_lecturas_sin_sesion(
    lectura: Lectura,
    sesion: str,
    base: Base,
    cliente: TestClient,
) -> None:
    """TC-B14 · CA-R1 — sin sesión (o con una que no existe): `401` `SIN_SESION`, sin asiento y sin ver nada del recurso."""
    asientos_antes = base.filas("SELECT count(*) FROM bitacora")

    respuesta = leer(
        cliente,
        lectura.ruta(uuid.uuid4()),
        uuid.uuid4() if sesion == "sesion_inexistente" else None,
    )

    exigir_error(
        respuesta,
        estado=401,
        esperado={"tipo": "SESION", "motivo": "SIN_SESION", "mensaje": MENSAJE_SIN_SESION},
        esquema="ErrorSesion",
    )
    assert base.filas("SELECT count(*) FROM bitacora") == asientos_antes, (
        "Una denegación anónima no se asienta en la bitácora"
    )


@pytest.mark.parametrize("lectura", POR_LECTURA)
def test_tkt017_cab08_las_lecturas_no_exigen_csrf(
    lectura: Lectura,
    entorno: Entorno,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    congelada: Congelada,
) -> None:
    """TC-B14 · CA-R1 · RNF-05 — son `GET`: un par CSRF que no coincide no las rechaza ni deja un `DENEGAR`.

    El doble envío protege lo que modifica estado; una lectura con la cookie `cimenta_csrf` distinta de la
    cabecera responde `200`. Mutante «`GET` con `verificar_origen`»: respondería `403` `ORIGEN_NO_VERIFICADO`.
    """
    lector = abrir_sesion(("COMPRAS",))

    respuesta = leer_con_par_csrf(
        cliente,
        lectura.ruta_de(entorno.obra_id, congelada.linea_base_id),
        lector.sesion_id,
        cookie_csrf=TOKEN_CSRF,
        cabecera_csrf=OTRO_TOKEN_CSRF,
    )

    assert respuesta.status_code == 200, respuesta.text
    assert base.filas("SELECT count(*) FROM bitacora WHERE accion = 'DENEGAR'") == [(0,)]


@pytest.mark.parametrize(
    ("consulta", "campo", "codigo", "mensaje"),
    [
        pytest.param(
            {"pagina": 0}, "pagina", "FUERA_DE_RANGO", MENSAJE_FUERA_DE_RANGO, id="pagina_cero"
        ),
        pytest.param(
            {"pagina": -1}, "pagina", "FUERA_DE_RANGO", MENSAJE_FUERA_DE_RANGO, id="pagina_negativa"
        ),
        pytest.param(
            {"pagina": "abc"}, "pagina", "FORMATO", MENSAJE_FORMATO, id="pagina_no_entera"
        ),
        pytest.param(
            {"tamano_pagina": 0},
            "tamano_pagina",
            "FUERA_DE_RANGO",
            MENSAJE_FUERA_DE_RANGO,
            id="tamano_cero",
        ),
        pytest.param(
            {"tamano_pagina": 201},
            "tamano_pagina",
            "FUERA_DE_RANGO",
            MENSAJE_FUERA_DE_RANGO,
            id="tamano_sobre_el_maximo",
        ),
        pytest.param(
            {"tipo_partida_id": "no-es-un-uuid"},
            "tipo_partida_id",
            "FORMATO",
            MENSAJE_FORMATO,
            id="tipo_partida_id_no_es_uuid",
        ),
    ],
)
def test_tkt017_cab08_conceptos_con_consulta_invalida(
    consulta: dict[str, object],
    campo: str,
    codigo: str,
    mensaje: str,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    congelada: Congelada,
) -> None:
    """TC-B14 · CA-B8 — `pagina` < 1, `tamano_pagina` fuera de 1 a 200 o un `tipo_partida_id` que no es UUID: `422` `VALIDACION` con el campo."""
    lector = abrir_sesion(("COMPRAS",))

    respuesta = leer(
        cliente, ruta_de_conceptos(congelada.linea_base_id), lector.sesion_id, **consulta
    )

    exigir_error(
        respuesta,
        estado=422,
        esperado={
            "tipo": "VALIDACION",
            "mensaje": MENSAJE_UN_CAMPO_INVALIDO,
            "errores": [{"campo": campo, "codigo": codigo, "mensaje": mensaje}],
        },
        esquema="ErrorValidacion",
    )


def test_tkt017_cab08_explosion_con_tipo_de_partida_que_no_es_uuid(
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    congelada: Congelada,
) -> None:
    """TC-B14 · CA-B8 — `tipo_partida_id` que no es UUID en la explosión: `422` `VALIDACION` con `FORMATO` en ese campo."""
    lector = abrir_sesion(("COMPRAS",))

    respuesta = leer(
        cliente, ruta_de_explosion(congelada.linea_base_id), lector.sesion_id, tipo_partida_id="x"
    )

    exigir_error(
        respuesta,
        estado=422,
        esperado={
            "tipo": "VALIDACION",
            "mensaje": MENSAJE_UN_CAMPO_INVALIDO,
            "errores": [
                {"campo": "tipo_partida_id", "codigo": "FORMATO", "mensaje": MENSAJE_FORMATO}
            ],
        },
        esquema="ErrorValidacion",
    )


@pytest.mark.parametrize("campo", ["q", "nivel"])
@pytest.mark.parametrize(
    "valor",
    [
        pytest.param("a\x00b", id="nul_en_medio"),
        pytest.param("\x00", id="solo_nul"),
    ],
)
def test_tkt017_cab08_conceptos_con_nul_en_q_o_nivel(
    campo: str,
    valor: str,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    congelada: Congelada,
    base: Base,
) -> None:
    """TC-B14 · CA-B8 — `q` o `nivel` con el carácter NUL (`%00`): `422` `VALIDACION` con `FORMATO` en ese campo.

    PostgreSQL no admite NUL en un texto: sin el `pattern` del parámetro la consulta llegaría a `psycopg` y
    la petición acabaría en `500`. Un rechazo de forma no escribe en la bitácora.
    """
    lector = abrir_sesion(("COMPRAS",))
    asientos_antes = base.filas("SELECT count(*) FROM bitacora")

    respuesta = leer(
        cliente, ruta_de_conceptos(congelada.linea_base_id), lector.sesion_id, **{campo: valor}
    )

    exigir_error(
        respuesta,
        estado=422,
        esperado={
            "tipo": "VALIDACION",
            "mensaje": MENSAJE_UN_CAMPO_INVALIDO,
            "errores": [{"campo": campo, "codigo": "FORMATO", "mensaje": MENSAJE_FORMATO}],
        },
        esquema="ErrorValidacion",
    )
    assert base.filas("SELECT count(*) FROM bitacora") == asientos_antes


# --------------------------------------------------------------------------- TC-B17 · CA-R1


def las_rutas_de_lectura(monkeypatch: pytest.MonkeyPatch) -> list[tuple[Lectura, APIRoute]]:
    """Cada lectura con su única `APIRoute` `GET`; si falta o está repetida, la prueba lo dice."""
    aplicacion = construir_aplicacion(monkeypatch)
    resultado: list[tuple[Lectura, APIRoute]] = []
    for lectura in LECTURAS:
        encontradas = [
            ruta
            for ruta in rutas_de(aplicacion.routes)
            if ruta.path == lectura.publicada and "GET" in (ruta.methods or ())
        ]
        assert len(encontradas) == 1, (
            f"La aplicación debe publicar exactamente un GET {lectura.publicada}; hay {len(encontradas)}"
        )
        resultado.append((lectura, encontradas[0]))
    return resultado


def test_tkt017_car1_las_rutas_de_lectura_estan_en_el_recorrido_de_la_aplicacion_completa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-B17 · CA-R1 · regla 11 — cada lectura es `def`, exige sesión con un solo `exigir_rol` y no lleva `verificar_origen`.

    Es el recorrido de `test_tkt006_enrutador.py` («`GET` con `exigir_rol`») hecho sobre estas cuatro rutas, con
    su `operation_id` del borrador. Anti-verde vacío: las rutas existen en el recorrido y llevan `sesion_vigente`.
    Mutantes «`async def`» y «`GET` sin `exigir_rol`».
    """
    from cimenta.identidad.api.dependencias import sesion_vigente, verificar_origen

    for lectura, ruta in las_rutas_de_lectura(monkeypatch):
        assert ruta.operation_id == lectura.operacion
        assert inspect.isfunction(ruta.endpoint)
        assert not inspect.iscoroutinefunction(ruta.endpoint), (
            f"{lectura.operacion} no puede ser async def"
        )
        cadena = list(llamadas(ruta.dependant))
        assert sesion_vigente in cadena
        assert verificar_origen not in cadena, "Una lectura no verifica el origen"
        roles = [c for c in cadena if getattr(c, "__name__", "") == "comprobar_rol"]
        assert len(roles) == 1, f"{lectura.operacion} debe declarar exactamente un exigir_rol"


def test_tkt017_car1_openapi_publica_las_lecturas_con_sesion_y_sin_csrf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-B17 · CA-R1 · M4 — `/openapi.json` declara `sesion` y no `csrf` en las cuatro lecturas."""
    contrato = publicado(monkeypatch)

    for lectura in LECTURAS:
        assert lectura.publicada in contrato["paths"], f"Falta {lectura.publicada} en /openapi.json"
        operacion = contrato["paths"][lectura.publicada]["get"]
        exigidos = {nombre for requisito in operacion.get("security", []) for nombre in requisito}
        assert "sesion" in exigidos, lectura.operacion
        assert "csrf" not in exigidos, lectura.operacion


# --------------------------------------------------------------------------- TC-B16 · CA-B9


def test_tkt017_cab09_el_borrador_publica_importe_costo_y_no_importe_venta() -> None:
    """TC-B16 · CA-B9 · PA-16.7 — `RenglonExplosion` publica `importe_costo` (cantidad × costo unitario, sin redondeos) y no `importe_venta`.

    Regresión del borrador, que ya trae el cambio: el nombre dice lo que es, un costo. Ningún ejemplo de
    `ExplosionInsumos` conserva el nombre viejo.
    """
    esquemas = borrador()["components"]["schemas"]
    renglon = esquemas["RenglonExplosion"]

    assert set(renglon["properties"]) == {
        "tipo_partida",
        "insumo",
        "cantidad_presupuestada",
        "rendimiento_congelado",
        "costo_unitario",
        "importe_costo",
    }
    assert "importe_costo" in renglon["required"]
    assert "importe_venta" not in renglon["required"]
    descripcion = renglon["properties"]["importe_costo"]["description"].lower()
    assert "cantidad presupuestada × costo unitario" in descripcion
    assert "sin redondeos intermedios" in descripcion
    for ejemplo in esquemas["ExplosionInsumos"]["examples"]:
        assert all("importe_venta" not in r and "importe_costo" in r for r in ejemplo["renglones"])


def test_tkt017_cab09_la_explosion_lleva_tkt_017_en_x_tickets_y_el_modelo_dice_costo() -> None:
    """TC-B16 · CA-B9 — `x-tickets` de `obtener_explosion_insumos` es exactamente `[TKT-017]`; `docs/03` describe la columna como cantidad × costo.

    La operación es de TKT-017 y de ningún otro ticket (decisión de la persona dueña): `TKT-016` no
    debe figurar en su `x-tickets`. La columna `explosion_presupuesto.importe_venta` no cambia de nombre (la migración `v0007` es de otro
    ticket); lo que cambia es lo que se dice de ella: un costo que no es el importe de venta del cliente.
    """
    operacion = borrador()["paths"]["/lineas-base/{linea_base_id}/explosion"]["get"]
    modelo = (RAIZ / "docs" / "03-modelo-datos.md").read_text(encoding="utf-8")
    lineas = [
        linea for linea in modelo.splitlines() if "numeric importe_venta" in linea and "Σ" in linea
    ]

    assert operacion["operationId"] == "obtener_explosion_insumos"
    assert operacion["x-tickets"] == ["TKT-017"]
    assert len(lineas) == 1, "docs/03 debe describir explosion_presupuesto.importe_venta"
    assert "costo unitario" in lineas[0]
    assert "No es un importe de venta del cliente" in lineas[0]


def test_tkt017_cab09_los_enums_publicados_de_las_lecturas_coinciden_con_el_borrador(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-B16 · CA-B8 · CA-R1 — `unidad` (de concepto e insumo) y `TipoPartida.clave` publican el `enum` del borrador, valor por valor.

    El cliente TypeScript se genera de `/openapi.json`: con `string` en lugar del enumerado, el cliente
    deja pasar una unidad o una clave que el contrato no admite. Validar la respuesta contra el borrador no
    lo detecta, porque `string` también cumple el enumerado.
    """
    contrato = publicado(monkeypatch)
    esperados: dict[str, list[str]] = {}
    for esquema in ("ListaConceptosLineaBase", "ExplosionInsumos"):
        assert esquema in contrato["components"]["schemas"], (
            f"El contrato publicado no tiene {esquema}"
        )
        del_borrador, _ = forma_de_componente(borrador(), esquema)
        enums = {ruta: valores for ruta, valores in del_borrador.items() if ruta.endswith(".enum")}
        esperados.update(
            {ruta: valores for ruta, valores in enums.items() if isinstance(valores, list)}
        )
        publicada, _ = forma_de_componente(contrato, esquema)
        assert {ruta: publicada.get(ruta) for ruta in enums} == enums

    assert set(esperados) == {
        "ListaConceptosLineaBase.elementos[].unidad.enum",
        "ListaConceptosLineaBase.elementos[].tipo_partida.clave.enum",
        "ExplosionInsumos.renglones[].tipo_partida.clave.enum",
        "ExplosionInsumos.renglones[].insumo.unidad.enum",
    }, "Anti-verde vacío: el borrador debe declarar los cuatro enumerados de las lecturas"
    assert esperados["ListaConceptosLineaBase.elementos[].unidad.enum"] == sorted(
        ["M2", "ML", "PZA", "KG", "CAJA", "SACO", "ROLLO", "JORNAL"]
    )


@pytest.mark.parametrize(
    "esquema",
    [
        "ListaConceptosLineaBase",
        "ConceptoLineaBase",
        "MetaPagina",
        "ExplosionInsumos",
        "RenglonExplosion",
    ],
)
def test_tkt017_cab09_la_forma_publicada_de_los_esquemas_de_lectura_coincide_con_el_borrador(
    esquema: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TC-B16 · CA-B8 · CA-B9 · CA-R1 — propiedades, `required`, tipos, `format` y nulabilidad de cada esquema publicado son los del borrador.

    Se comparan, con los `$ref` resueltos, el esquema y todo lo que cuelga de él (`TipoPartida`,
    `InsumoResumen`, `MetaPagina`). `RenglonExplosion` publica `importe_costo` y no `importe_venta`. Los
    componentes de objeto o enumerado del borrador deben existir con su nombre en el publicado, y el
    publicado no debe duplicar ninguno bajo otro nombre con la misma forma.
    """
    contrato = publicado(monkeypatch)
    assert esquema in contrato["components"]["schemas"], f"El contrato publicado no tiene {esquema}"

    del_borrador, componentes_borrador = forma_de_componente(borrador(), esquema)
    publicada, componentes_publicados = forma_de_componente(contrato, esquema)

    assert diferencias_de_forma(del_borrador, publicada) == []
    faltan = sorted(componentes_borrador - set(contrato["components"]["schemas"]))
    assert faltan == [], f"Faltan componentes con el nombre del borrador: {faltan}"
    assert componentes_duplicados(contrato, componentes_publicados) == []


@pytest.mark.parametrize("lectura", POR_LECTURA)
def test_tkt017_cab09_la_respuesta_y_los_parametros_publicados_son_los_del_borrador(
    lectura: Lectura, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TC-B16 · CA-B8 · CA-R1 — la respuesta `200` y los parámetros de cada lectura publicados son los del borrador.

    Parámetros: nombre, ubicación, obligatoriedad, tipo, `format`, `minimum`, `maximum` y valor por omisión.
    `pagina` es entero ≥ 1 con 1 por omisión; `tamano_pagina`, de 1 a 200 con 50; `tipo_partida_id`, UUID;
    `nivel` y `q`, cadena. La respuesta de `listar_lineas_base` es un arreglo de `LineaBase`.
    """
    contrato = publicado(monkeypatch)
    sin_prefijo = lectura.publicada.removeprefix("/api/v1")
    assert lectura.publicada in contrato["paths"], f"Falta {lectura.publicada} en /openapi.json"

    parametros_borrador = parametros_de(borrador(), sin_prefijo, "get")
    parametros_publicados = parametros_de(contrato, lectura.publicada, "get")
    forma_borrador, _ = forma_de(
        borrador(), esquema_de_respuesta_200(borrador(), sin_prefijo, "get"), "respuesta"
    )
    forma_publicada, _ = forma_de(
        contrato, esquema_de_respuesta_200(contrato, lectura.publicada, "get"), "respuesta"
    )

    assert parametros_publicados == parametros_borrador
    assert diferencias_de_forma(forma_borrador, forma_publicada) == []


# --------------------------------------------------------------------------- TC-B19 · CA-B8, CA-R1


def test_tkt017_las_cuatro_lecturas_estan_entre_las_operaciones_de_presupuesto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-B19 (fila B4) · CA-B8 · CA-R1 — el borrador lleva `TKT-017` en las cuatro lecturas y la aplicación las publica con su `operationId`.

    El conjunto exacto `(método, ruta, operationId)` de `presupuesto` lo fija `TC-B19` en
    `test_tkt017_api_congelado.py`, cuya lista `IMPLEMENTADAS_DE_PRESUPUESTO` ya incluye estas cuatro.
    """
    contrato = publicado(monkeypatch)

    for lectura in LECTURAS:
        operacion_borrador = borrador()["paths"][lectura.publicada.removeprefix("/api/v1")]["get"]
        assert operacion_borrador["operationId"] == lectura.operacion
        assert "TKT-017" in operacion_borrador["x-tickets"]
        assert lectura.publicada in contrato["paths"], f"Falta {lectura.publicada} en /openapi.json"
        publicada = contrato["paths"][lectura.publicada]["get"]
        assert publicada["operationId"] == lectura.operacion
        assert "presupuesto" in publicada["tags"]


# --------------------------------------------------------------------------- órdenes totales y contrato declarado


def test_tkt017_cab08_lineas_base_de_obra_desempata_la_version_por_id(
    motor_aplicacion: Engine,
) -> None:
    """TC-B13 · CA-B8 · RN-01 — el `ORDER BY` de `lineas_base_completas_de_obra` es total: `version DESC` y, a igual versión, `id`.

    `linea_base` no tiene UNIQUE sobre `(obra_id, version)` (PA-T3): dos filas con la misma versión son
    posibles, así que el orden no puede depender de una restricción; el `ORDER BY` sin desempate le deja
    al plan decidir. El orden del
    resultado no se puede afirmar de forma estable (un plan secuencial devolvería el de inserción aun sin
    el desempate), así que se afirma la sentencia que sale al cursor, que es lo que lo garantiza.
    """
    capturadas: list[str] = []

    def registrar(
        conexion: object,
        cursor: object,
        sentencia: str,
        parametros: object,
        contexto: object,
        ejecutar_muchas: bool,
    ) -> None:
        capturadas.append(" ".join(sentencia.split()))

    event.listen(motor_aplicacion, "before_cursor_execute", registrar)
    try:
        with Session(motor_aplicacion) as sesion:
            repositorio_linea_base.lineas_base_completas_de_obra(sesion, uuid.uuid4())
    finally:
        event.remove(motor_aplicacion, "before_cursor_execute", registrar)

    lecturas = [sentencia for sentencia in capturadas if "FROM linea_base" in sentencia]
    assert len(lecturas) == 1, capturadas
    assert "ORDER BY " in lecturas[0], lecturas[0]
    assert lecturas[0].rsplit("ORDER BY ", 1)[1] == "linea_base.version DESC, linea_base.id"


CODIGOS_DE_LAS_DOS_LECTURAS = ["200", "401", "403", "404", "422"]
LECTURAS_CON_PARAMETROS = [
    pytest.param(la_lectura("listar_conceptos_linea_base"), id="listar_conceptos_linea_base"),
    pytest.param(la_lectura("obtener_explosion_insumos"), id="obtener_explosion_insumos"),
]
PARAMETROS_DE_TEXTO = ["q", "nivel"]


def _operacion_get(documento: Mapping[str, Any], ruta: str) -> dict[str, Any]:
    operacion: dict[str, Any] = documento["paths"][ruta]["get"]
    return operacion


def _referencia_del_422(operacion: Mapping[str, Any], documento: Mapping[str, Any]) -> str | None:
    """El componente de esquema al que apunta el `422` de una operación, resolviendo `#/components/responses/…`."""
    respuesta = operacion["responses"].get("422")
    if respuesta is None:
        return None
    if "$ref" in respuesta:
        respuesta = documento["components"]["responses"][respuesta["$ref"].rsplit("/", 1)[-1]]
    esquema = respuesta["content"]["application/json"]["schema"]
    return str(esquema["$ref"]).rsplit("/", 1)[-1]


@pytest.mark.parametrize("lectura", LECTURAS_CON_PARAMETROS)
def test_tkt017_cab08_el_borrador_declara_el_422_de_las_lecturas_con_parametros(
    lectura: Lectura,
) -> None:
    """TC-B14 · CA-B8 — el borrador declara `200`, `401`, `403`, `404` y `422` (`ErrorValidacion`) en las lecturas que tienen parámetros de consulta.

    Las dos operaciones rechazan con `422` un `tipo_partida_id` que no es UUID (y la de conceptos, `pagina`,
    `tamano_pagina`, `q` y `nivel`): el contrato que se genera para el cliente debe decirlo. El `422` apunta
    a `ErrorValidacion` por la respuesta compartida `ErrorDeForma`.
    """
    operacion = _operacion_get(borrador(), lectura.publicada.removeprefix("/api/v1"))

    assert sorted(operacion["responses"]) == CODIGOS_DE_LAS_DOS_LECTURAS
    assert _referencia_del_422(operacion, borrador()) == "ErrorValidacion"


@pytest.mark.parametrize("lectura", LECTURAS_CON_PARAMETROS)
def test_tkt017_cab08_los_codigos_publicados_de_las_lecturas_estan_declarados_en_el_borrador(
    lectura: Lectura, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TC-B14 · CA-B8 — todo código de respuesta que la aplicación publica en estas lecturas está declarado en el borrador, y el `200` y el `422` son de los dos.

    La aplicación publica hoy solo `200` y `422` (FastAPI los añade por omisión; los errores `401`, `403` y
    `404` los documenta el borrador y ninguna ruta de `cimenta/` los declara: es la deuda de TKT-061). Lo que
    sí se exige es que el borrador no omita ninguno de los que la aplicación publica.
    """
    contrato = publicado(monkeypatch)
    sin_prefijo = lectura.publicada.removeprefix("/api/v1")
    del_borrador = set(_operacion_get(borrador(), sin_prefijo)["responses"])
    de_la_aplicacion = set(_operacion_get(contrato, lectura.publicada)["responses"])

    assert {"200", "422"} <= de_la_aplicacion, "Anti-verde vacío: la aplicación publica 200 y 422"
    assert de_la_aplicacion <= del_borrador, sorted(de_la_aplicacion - del_borrador)


def _patrones(esquema: Mapping[str, Any]) -> list[str]:
    """Todo `pattern` de un esquema de parámetro, también dentro de un `anyOf` con `null`."""
    encontrados = [str(esquema["pattern"])] if "pattern" in esquema else []
    for variante in esquema.get("anyOf", []):
        encontrados.extend(_patrones(variante))
    return encontrados


def _patron_del_parametro(documento: Mapping[str, Any], ruta: str, nombre: str) -> str:
    operacion = _operacion_get(documento, ruta)
    parametro = next(p for p in operacion["parameters"] if p["name"] == nombre)
    patrones = _patrones(parametro["schema"])
    assert len(patrones) == 1, f"{nombre} debe llevar exactamente un pattern: {patrones}"
    return patrones[0]


@pytest.mark.parametrize("nombre", PARAMETROS_DE_TEXTO)
def test_tkt017_cab08_q_y_nivel_publican_el_patron_sin_nul_del_borrador(
    nombre: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """TC-B14 · CA-B8 — `q` y `nivel` declaran un `pattern` que excluye el NUL, en el borrador y en lo publicado, y los dos se comportan igual.

    El rechazo del NUL (`422` `FORMATO`, `test_tkt017_cab08_conceptos_con_nul_en_q_o_nivel`) existe en la
    aplicación; este contrato debe decirlo para que el cliente generado no lo deje pasar. Se comparan los
    dos patrones por lo que aceptan y rechazan, no por su escritura.
    """
    ruta = "/lineas-base/{linea_base_id}/conceptos"
    del_borrador = re.compile(_patron_del_parametro(borrador(), ruta, nombre))
    de_la_aplicacion = re.compile(
        _patron_del_parametro(publicado(monkeypatch), f"/api/v1{ruta}", nombre)
    )

    for texto in ("", "abc", "100%", "a b_c/d", "ñandú"):
        assert de_la_aplicacion.search(texto) is not None, texto
        assert del_borrador.search(texto) is not None, texto
    for texto in ("\x00", "a\x00b", "abc\x00"):
        assert de_la_aplicacion.search(texto) is None, repr(texto)
        assert del_borrador.search(texto) is None, repr(texto)


def test_tkt017_cab08_la_unidad_publicada_coincide_con_las_admitidas_del_dominio() -> None:
    """TC-B16 · CA-B8 — el enumerado `Unidad` de la API tiene exactamente las unidades que el catálogo del dominio admite.

    Si el dominio admite una unidad que la API no publica, una lectura de esa unidad fallaría al serializar
    (`500`); si la API publica una que el dominio rechaza, el cliente ofrecería un valor imposible.
    """
    assert {unidad.value for unidad in Unidad} == UNIDADES_ADMITIDAS
