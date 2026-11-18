"""Reglas puras del ciclo de vida de la obra, TKT-012b (fila A2, TC-05 a TC-11 y TC-13).

Pytest puro, sin Docker ni base. Define la API que el desarrollador implementa en
`cimenta/presupuesto/dominio/ciclo_vida_obra.py`:

* `EstadoObraDominio` (`StrEnum`): `PLANEACION`, `ACTIVA`, `SUSPENDIDA`, `CERRADA`, con el texto
  idéntico al de `ck_obra_estado`.
* `OperacionObra` (`StrEnum`): `SUSPENDER`, `REACTIVAR`, `CERRAR`, en ese orden de declaración.
* `evaluar_transicion(estado, operacion)` devuelve `TransicionAdmitida(estado_destino=...)` o
  `TransicionRechazada(estado_actual=..., operaciones_admitidas=(...))`. Las operaciones admitidas
  van como `tuple[OperacionObra, ...]` en el orden de declaración de `OperacionObra`.
* `operaciones_admitidas(estado)` devuelve esa misma tupla; es la fuente de las `acciones` del `409`.
* `admite_edicion(estado)` es falso solo en `CERRADA` (D-3).
* `cambios_efectivos(actuales, propuestos)`:
  `actuales` es un `DatosObraEditables` (nombre, domicilio, retencion_destajo_pct, fondo_garantia_pct,
  iva_acreditable, umbral_alerta_pct; los porcentajes son `Porcentaje`) y `propuestos` un `Mapping`
  de nombre de campo a valor propuesto. **Ausente = no propuesto**: una clave que falta no cambia
  nada. Solo `umbral_alerta_pct` admite `None` como valor propuesto (borrar el umbral). Devuelve
  `CambiosEfectivos(antes, despues)`, dos `Mapping[str, valor]` con las mismas claves: solo los
  campos cuyo valor propuesto difiere del actual. Los valores son los objetos de dominio
  (`Porcentaje`, `str`, `bool`, `None`), sin serializar. Dos `Porcentaje` iguales por valor
  (`0.10` y `0.100000`) no son un cambio.

Nace en rojo: las funciones del esqueleto lanzan `NotImplementedError`. La excepción es TC-13
(pureza), que nace verde porque el esqueleto ya cumple la lista blanca; es una guarda de regresión.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

from cimenta.presupuesto.dominio.ciclo_vida_obra import (
    CambiosEfectivos,
    DatosObraEditables,
    EstadoObraDominio,
    OperacionObra,
    TransicionAdmitida,
    TransicionRechazada,
    admite_edicion,
    cambios_efectivos,
    evaluar_transicion,
    operaciones_admitidas,
)
from herramientas.verificar_float import buscar_float
from tipos_base import Porcentaje

PLANEACION = EstadoObraDominio.PLANEACION
ACTIVA = EstadoObraDominio.ACTIVA
SUSPENDIDA = EstadoObraDominio.SUSPENDIDA
CERRADA = EstadoObraDominio.CERRADA
SUSPENDER = OperacionObra.SUSPENDER
REACTIVAR = OperacionObra.REACTIVAR
CERRAR = OperacionObra.CERRAR

# Tabla D-2 del diseño: origen -> operaciones admitidas, en el orden de `OperacionObra`.
ADMITIDAS_POR_ESTADO = {
    PLANEACION: (CERRAR,),
    ACTIVA: (SUSPENDER, CERRAR),
    SUSPENDIDA: (REACTIVAR, CERRAR),
    CERRADA: (),
}
# Las cinco transiciones admitidas: (origen, operación, destino).
ADMITIDAS = [
    (ACTIVA, SUSPENDER, SUSPENDIDA),
    (SUSPENDIDA, REACTIVAR, ACTIVA),
    (ACTIVA, CERRAR, CERRADA),
    (SUSPENDIDA, CERRAR, CERRADA),
    (PLANEACION, CERRAR, CERRADA),
]
# Las siete combinaciones prohibidas de CA-9.
PROHIBIDAS = [
    (PLANEACION, SUSPENDER),
    (PLANEACION, REACTIVAR),
    (ACTIVA, REACTIVAR),
    (SUSPENDIDA, SUSPENDER),
    (CERRADA, SUSPENDER),
    (CERRADA, REACTIVAR),
    (CERRADA, CERRAR),
]


def _rechazo(resultado: object) -> TransicionRechazada:
    assert isinstance(resultado, TransicionRechazada), resultado
    return resultado


# --- TC-05 y TC-06 · transiciones admitidas ---------------------------------------------------


@pytest.mark.parametrize(
    ("origen", "operacion", "destino"),
    [
        pytest.param(ACTIVA, SUSPENDER, SUSPENDIDA, id="activa-suspender"),
        pytest.param(SUSPENDIDA, REACTIVAR, ACTIVA, id="suspendida-reactivar"),
        pytest.param(ACTIVA, CERRAR, CERRADA, id="activa-cerrar"),
        pytest.param(SUSPENDIDA, CERRAR, CERRADA, id="suspendida-cerrar"),
    ],
)
def test_hdu001_esc20_transicion_admitida_lleva_al_estado_de_la_tabla(
    origen: EstadoObraDominio, operacion: OperacionObra, destino: EstadoObraDominio
) -> None:
    """TC-05 · CA-8 · RN-25 — las cuatro transiciones de D-2 desde `ACTIVA` y `SUSPENDIDA` se admiten."""
    assert evaluar_transicion(origen, operacion) == TransicionAdmitida(estado_destino=destino)


def test_hdu001_esc20_planeacion_cerrar_se_admite_y_lleva_a_cerrada() -> None:
    """TC-06 · CA-8 (ejemplo añadido, D-DIS-6) — una obra que nunca arrancó se cierra sin eliminarse."""
    assert evaluar_transicion(PLANEACION, CERRAR) == TransicionAdmitida(estado_destino=CERRADA)


def test_hdu001_esc20_solo_las_cinco_transiciones_de_la_tabla_se_admiten() -> None:
    """TC-05 · CA-8, CA-9 — de las doce combinaciones estado x operación, admite exactamente las cinco."""
    admitidas = {
        (estado, operacion)
        for estado in EstadoObraDominio
        for operacion in OperacionObra
        if isinstance(evaluar_transicion(estado, operacion), TransicionAdmitida)
    }

    assert admitidas == {(origen, operacion) for origen, operacion, _ in ADMITIDAS}


def test_tkt012b_ca8_planeacion_a_activa_no_es_una_operacion_del_ciclo_de_vida() -> None:
    """CA-8, CA-R1 — `PLANEACION -> ACTIVA` solo ocurre por el congelado: ninguna operación lo logra."""
    destinos_desde_planeacion = {
        resultado.estado_destino
        for operacion in OperacionObra
        if isinstance(resultado := evaluar_transicion(PLANEACION, operacion), TransicionAdmitida)
    }

    assert ACTIVA not in destinos_desde_planeacion


# --- TC-07 · rechazos con el estado actual y las operaciones que sí admite --------------------


@pytest.mark.parametrize(
    ("origen", "operacion"),
    [
        pytest.param(origen, operacion, id=f"{origen.value.lower()}-{operacion.value.lower()}")
        for origen, operacion in PROHIBIDAS
    ],
)
def test_tkt012b_ca9_transicion_no_admitida_rechaza_con_estado_y_operaciones_admitidas(
    origen: EstadoObraDominio, operacion: OperacionObra
) -> None:
    """TC-07 · CA-9 · RN-25 — el rechazo trae el estado actual y las operaciones que sí admite (el dato)."""
    rechazo = _rechazo(evaluar_transicion(origen, operacion))

    assert rechazo.estado_actual == origen
    assert rechazo.operaciones_admitidas == ADMITIDAS_POR_ESTADO[origen]


def test_tkt012b_ca9_las_siete_combinaciones_prohibidas_son_las_unicas_que_rechazan() -> None:
    """TC-07 · CA-9 — el conjunto que rechaza es exactamente el de las siete combinaciones de CA-9."""
    rechazadas = {
        (estado, operacion)
        for estado in EstadoObraDominio
        for operacion in OperacionObra
        if isinstance(evaluar_transicion(estado, operacion), TransicionRechazada)
    }

    assert rechazadas == set(PROHIBIDAS)


def test_tkt012b_ca9_cerrada_es_terminal_y_su_rechazo_no_ofrece_ninguna_operacion() -> None:
    """TC-07 · CA-9 — desde `CERRADA` ninguna operación se admite y la lista que ofrece está vacía."""
    for operacion in OperacionObra:
        rechazo = _rechazo(evaluar_transicion(CERRADA, operacion))
        assert rechazo.operaciones_admitidas == ()


# --- operaciones_admitidas: la fuente de las `acciones` del 409 -------------------------------


@pytest.mark.parametrize(
    ("estado", "esperadas"),
    [
        pytest.param(estado, esperadas, id=estado.value.lower())
        for estado, esperadas in ADMITIDAS_POR_ESTADO.items()
    ],
)
def test_tkt012b_ca6_operaciones_admitidas_por_estado(
    estado: EstadoObraDominio, esperadas: tuple[OperacionObra, ...]
) -> None:
    """TC-07 · CA-6, CA-9 — por estado: `PLANEACION` solo cierra (nunca ofrece suspender, objeción 5)."""
    assert operaciones_admitidas(estado) == esperadas


def test_tkt012b_ca6_operaciones_admitidas_coincide_con_lo_que_evaluar_transicion_admite() -> None:
    """TC-07 · CA-6, CA-9 — una fuente, dos funciones: lo que se ofrece es lo que no daría `409`."""
    for estado in EstadoObraDominio:
        ofrecidas = set(operaciones_admitidas(estado))
        admitidas = {
            operacion
            for operacion in OperacionObra
            if isinstance(evaluar_transicion(estado, operacion), TransicionAdmitida)
        }
        assert ofrecidas == admitidas, estado


def test_tkt012b_ca8_los_estados_y_operaciones_son_los_textos_de_la_base_y_del_contrato() -> None:
    """CA-8 — `EstadoObraDominio` repite `ck_obra_estado` y `OperacionObra` los verbos de la bitácora."""
    assert [estado.value for estado in EstadoObraDominio] == [
        "PLANEACION",
        "ACTIVA",
        "SUSPENDIDA",
        "CERRADA",
    ]
    assert [operacion.value for operacion in OperacionObra] == ["SUSPENDER", "REACTIVAR", "CERRAR"]


# --- TC-08 · admite_edicion --------------------------------------------------------------------


@pytest.mark.parametrize("estado", [PLANEACION, ACTIVA, SUSPENDIDA])
def test_tkt012b_ca1_admite_edicion_en_planeacion_activa_y_suspendida(
    estado: EstadoObraDominio,
) -> None:
    """TC-08 · CA-1, D-3 — una obra `SUSPENDIDA` sí se edita (la edición no exige reactivar antes)."""
    assert admite_edicion(estado) is True


def test_tkt012b_ca4_cerrada_no_admite_edicion() -> None:
    """TC-08 · CA-4 · RN-25 — solo `CERRADA` bloquea la edición."""
    assert admite_edicion(CERRADA) is False


# --- TC-09 a TC-11 · cambios_efectivos ---------------------------------------------------------


def _obra_actual(**cambios: object) -> DatosObraEditables:
    """La obra «AP-058-25» con valores de partida; `cambios` sustituye campos por nombre."""
    datos: dict[str, object] = {
        "nombre": "Union Square F2",
        "domicilio": "Av. Reforma 100, CDMX",
        "retencion_destajo_pct": Porcentaje("0.050000"),
        "fondo_garantia_pct": Porcentaje("0.050000"),
        "iva_acreditable": True,
        "umbral_alerta_pct": Porcentaje("0.200000"),
    }
    datos.update(cambios)
    return DatosObraEditables(**datos)  # type: ignore[arg-type]


def test_tkt012b_ca1_cambios_efectivos_trae_antes_y_despues_solo_de_los_campos_que_cambian() -> (
    None
):
    """TC-09 · CA-1 · RN-25 — un valor igual al actual no cuenta; antes y después traen solo lo cambiado."""
    resultado = cambios_efectivos(
        _obra_actual(),
        {
            "nombre": "Union Square F2 (ampliación)",
            "domicilio": "Av. Reforma 100, CDMX",  # igual: no cuenta
            "retencion_destajo_pct": Porcentaje("0.100000"),
            "fondo_garantia_pct": Porcentaje("0.05"),  # igual por valor aunque con otra escala
            "iva_acreditable": True,  # igual: no cuenta
        },
    )

    assert isinstance(resultado, CambiosEfectivos)
    assert dict(resultado.antes) == {
        "nombre": "Union Square F2",
        "retencion_destajo_pct": Porcentaje("0.05"),
    }
    assert dict(resultado.despues) == {
        "nombre": "Union Square F2 (ampliación)",
        "retencion_destajo_pct": Porcentaje("0.1"),
    }


@pytest.mark.parametrize(
    ("campo", "nuevo", "anterior"),
    [
        pytest.param("nombre", "Otro nombre", "Union Square F2", id="nombre"),
        pytest.param("domicilio", "Calle Nueva 5", "Av. Reforma 100, CDMX", id="domicilio"),
        pytest.param(
            "retencion_destajo_pct", Porcentaje("0.07"), Porcentaje("0.05"), id="retencion"
        ),
        pytest.param("fondo_garantia_pct", Porcentaje("0.09"), Porcentaje("0.05"), id="fondo"),
        pytest.param("iva_acreditable", False, True, id="iva-a-falso"),
        pytest.param("umbral_alerta_pct", Porcentaje("0.30"), Porcentaje("0.20"), id="umbral"),
    ],
)
def test_tkt012b_ca1_cada_campo_editable_por_separado_es_un_cambio(
    campo: str, nuevo: object, anterior: object
) -> None:
    """TC-09 · CA-1 — cada uno de los seis campos, solo, produce exactamente su par antes/después.

    `iva_acreditable` a `False` cubre el valor falso: no es «ausente».
    """
    resultado = cambios_efectivos(_obra_actual(), {campo: nuevo})  # type: ignore[dict-item]

    assert dict(resultado.antes) == {campo: anterior}
    assert dict(resultado.despues) == {campo: nuevo}


def test_tkt012b_ca1_cambios_efectivos_no_modifica_los_datos_actuales() -> None:
    """TC-09 · CA-1 — los actuales son inmutables: la función devuelve el cambio y no lo aplica."""
    actuales = _obra_actual()

    cambios_efectivos(actuales, {"nombre": "Otro nombre"})

    assert actuales == _obra_actual()


def test_tkt012b_ca1_clave_desconocida_se_ignora() -> None:
    """TC-09 · CA-1 — una clave que no es campo editable (`codigo`, `estado`...) no entra al cambio.

    El dominio no lanza: el `422` de los campos fijos lo da el DTO (CA-2). Solo cuentan los seis
    campos editables.
    """
    resultado = cambios_efectivos(
        _obra_actual(),
        {"codigo": "AP-999-26", "estado": "CERRADA", "nombre": "Otro nombre"},
    )

    assert dict(resultado.antes) == {"nombre": "Union Square F2"}
    assert dict(resultado.despues) == {"nombre": "Otro nombre"}


def test_tkt012b_ca1_solo_claves_desconocidas_devuelve_vacio() -> None:
    """TC-10 · CA-1 — con solo claves desconocidas no hay cambio efectivo (ni asiento, S-2)."""
    resultado = cambios_efectivos(_obra_actual(), {"codigo": "AP-999-26"})

    assert dict(resultado.antes) == {}
    assert dict(resultado.despues) == {}


def test_tkt012b_ca1_sin_cambios_reales_devuelve_vacio() -> None:
    """TC-10 · CA-1 variante — todos los valores propuestos iguales a los actuales: ni antes ni después."""
    resultado = cambios_efectivos(
        _obra_actual(),
        {
            "nombre": "Union Square F2",
            "domicilio": "Av. Reforma 100, CDMX",
            "retencion_destajo_pct": Porcentaje("0.05"),
            "fondo_garantia_pct": Porcentaje("0.05"),
            "iva_acreditable": True,
            "umbral_alerta_pct": Porcentaje("0.2"),
        },
    )

    assert dict(resultado.antes) == {}
    assert dict(resultado.despues) == {}


def test_tkt012b_ca1_sin_propuestos_devuelve_vacio() -> None:
    """TC-10 · CA-1 variante — un mapa de propuestos sin claves no cambia nada (todo ausente)."""
    resultado = cambios_efectivos(_obra_actual(), {})

    assert dict(resultado.antes) == {}
    assert dict(resultado.despues) == {}


def test_tkt012b_ca1_umbral_none_explicito_borra_el_umbral() -> None:
    """TC-11 · CA-1 variante — `umbral_alerta_pct: None` propuesto sobre un umbral existente es un borrado."""
    resultado = cambios_efectivos(_obra_actual(), {"umbral_alerta_pct": None})

    assert dict(resultado.antes) == {"umbral_alerta_pct": Porcentaje("0.2")}
    assert dict(resultado.despues) == {"umbral_alerta_pct": None}


def test_tkt012b_ca1_umbral_ausente_conserva_el_umbral() -> None:
    """TC-11 · CA-1 variante — sin la clave `umbral_alerta_pct`, el umbral no aparece en el cambio."""
    resultado = cambios_efectivos(_obra_actual(), {"nombre": "Otro nombre"})

    assert "umbral_alerta_pct" not in resultado.antes
    assert "umbral_alerta_pct" not in resultado.despues
    assert dict(resultado.despues) == {"nombre": "Otro nombre"}


def test_tkt012b_ca1_umbral_none_sobre_umbral_ya_vacio_no_es_cambio() -> None:
    """TC-11 · CA-1 variante — borrar un umbral que ya no existe no cuenta (sin asiento, S-2)."""
    resultado = cambios_efectivos(_obra_actual(umbral_alerta_pct=None), {"umbral_alerta_pct": None})

    assert dict(resultado.antes) == {}
    assert dict(resultado.despues) == {}


def test_tkt012b_ca1_umbral_nuevo_sobre_umbral_vacio_es_cambio_desde_none() -> None:
    """TC-11 · CA-1 variante — fijar un umbral donde no había: el antes es `None`, no una clave ausente."""
    resultado = cambios_efectivos(
        _obra_actual(umbral_alerta_pct=None), {"umbral_alerta_pct": Porcentaje("0.15")}
    )

    assert dict(resultado.antes) == {"umbral_alerta_pct": None}
    assert dict(resultado.despues) == {"umbral_alerta_pct": Porcentaje("0.15")}


def test_tkt012b_ca1_umbral_cero_no_es_lo_mismo_que_ningun_umbral() -> None:
    """TC-11 · CA-1 variante — `0` y `None` difieren: pasar de `0` a `None` es un cambio (no se compara por verdad)."""
    resultado = cambios_efectivos(
        _obra_actual(umbral_alerta_pct=Porcentaje("0")), {"umbral_alerta_pct": None}
    )

    assert dict(resultado.antes) == {"umbral_alerta_pct": Porcentaje("0")}
    assert dict(resultado.despues) == {"umbral_alerta_pct": None}


def test_tkt012b_ca1_porcentaje_cero_propuesto_sobre_cinco_por_ciento_es_cambio() -> None:
    """TC-09 · CA-1 — un porcentaje propuesto en `0` es un valor, no «ausente» ni «sin cambio»."""
    resultado = cambios_efectivos(_obra_actual(), {"retencion_destajo_pct": Porcentaje("0")})

    assert dict(resultado.antes) == {"retencion_destajo_pct": Porcentaje("0.05")}
    assert dict(resultado.despues) == {"retencion_destajo_pct": Porcentaje("0")}


# --- TC-13 · pureza ----------------------------------------------------------------------------

BACKEND = Path(__file__).resolve().parents[1]
DOMINIO_PRESUPUESTO = BACKEND / "cimenta" / "presupuesto" / "dominio"
MODULOS_PUROS = ("ciclo_vida_obra.py", "historial_obra.py")
PAQUETE_PROPIO = "cimenta.presupuesto.dominio"
PAQUETE_TIPOS_BASE = "tipos_base"
# Módulos de E/S y de reloj que la lista blanca de la biblioteca estándar excluye (ADR-021).
RELOJ_Y_ES = frozenset(
    {
        "datetime",
        "os",
        "socket",
        "time",
        "pathlib",
        "io",
        "random",
        "subprocess",
        "tempfile",
        "shutil",
        "asyncio",
        "threading",
        "http",
        "urllib",
        "ssl",
    }
)


def _modulos_importados(arbol: ast.Module) -> list[str]:
    modulos: list[str] = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            modulos.extend(alias.name for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom):
            modulos.append(f"{'.' * nodo.level}{nodo.module or ''}")
    return modulos


def _permitido(modulo: str) -> bool:
    if modulo.startswith(".") or modulo.startswith(PAQUETE_PROPIO):
        return True
    raiz = modulo.split(".")[0]
    if raiz == PAQUETE_TIPOS_BASE:
        return True
    return raiz in sys.stdlib_module_names and raiz not in RELOJ_Y_ES


@pytest.mark.parametrize("modulo", MODULOS_PUROS)
def test_tkt012b_pureza_solo_biblioteca_estandar_y_tipos_base(modulo: str) -> None:
    """TC-13 · regla 2 de CLAUDE.md, ADR-021 — el módulo importa solo biblioteca estándar sin E/S ni
    reloj, `tipos_base` y su propio paquete. Nace verde (el esqueleto ya cumple): es una guarda."""
    archivo = DOMINIO_PRESUPUESTO / modulo
    assert archivo.is_file(), f"Falta {archivo}"  # anti-verde vacío
    arbol = ast.parse(archivo.read_text(encoding="utf-8"), filename=str(archivo))

    prohibidos = [m for m in _modulos_importados(arbol) if not _permitido(m)]

    assert prohibidos == [], f"{modulo} importa fuera de la lista blanca: {prohibidos}"


@pytest.mark.parametrize("modulo", MODULOS_PUROS)
def test_tkt012b_pureza_sin_float_en_firmas_ni_en_el_cuerpo(modulo: str) -> None:
    """TC-13 · regla 1 de CLAUDE.md — ninguna anotación (`verificar_float`), ninguna llamada `float(...)`
    ni literal flotante: los porcentajes son `Porcentaje` y se construyen desde cadena."""
    archivo = DOMINIO_PRESUPUESTO / modulo
    assert archivo.is_file(), f"Falta {archivo}"  # anti-verde vacío
    codigo = archivo.read_text(encoding="utf-8")
    arbol = ast.parse(codigo, filename=str(archivo))

    en_anotaciones = buscar_float(codigo, archivo)
    nombres_float = [
        nodo.lineno for nodo in ast.walk(arbol) if isinstance(nodo, ast.Name) and nodo.id == "float"
    ]
    literales_float = [
        nodo.lineno
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.Constant) and isinstance(nodo.value, float)
    ]

    assert en_anotaciones == []
    assert nombres_float == []
    assert literales_float == []
