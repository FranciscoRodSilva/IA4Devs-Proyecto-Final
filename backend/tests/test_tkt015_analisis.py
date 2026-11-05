"""TKT-015a · Casos de uso de análisis contra PostgreSQL (fila A6): TC-24 a TC-39."""

from __future__ import annotations

import threading
import time
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session, sessionmaker

from cimenta.presupuesto.dominio.catalogo import (
    CatalogoLeido,
    ConceptoLeido,
    Ruta,
)
from cimenta.presupuesto.dominio.clasificacion_importacion import (
    TIPO_POR_CAUSA,
    clasificar_hallazgo,
    detectar_duplicados,
    errores_sin_apu,
)
from cimenta.presupuesto.dominio.importacion import (
    ErrorImportacion,
    MotivoInterrupcion,
    TipoErrorImportacion,
    error_de_interrupcion,
)
from cimenta.presupuesto.infraestructura.preparacion_json import FORMATO_PREPARACION
from contrato_error import ConflictoEstado, NoEncontrado
from herramientas.soporte_tkt015 import (
    CampoConcepto,
    catalogo_con_descripciones,
    hallazgo_ejemplo,
    libro_sintetico,
)

if TYPE_CHECKING:
    from conftest import Conectar, DatosPresupuesto, LibroCatalogo

_TABLAS_SIN_CAMBIO = (
    "concepto",
    "insumo",
    "linea_base",
    "linea_base_concepto",
    "explosion_presupuesto",
    "presupuesto_control",
)


@pytest.fixture
def fabrica_sesiones(motor_aplicacion) -> sessionmaker[Session]:
    return sessionmaker(bind=motor_aplicacion, expire_on_commit=False)


def _contar(conectar: Conectar, base: str, tabla: str) -> int:
    with conectar("aplicacion", base) as conn:
        fila = conn.execute(f"SELECT count(*) FROM {tabla}").fetchone()
    assert fila is not None
    return int(fila[0])


def _fila_importacion(conectar: Conectar, base: str, importacion_id: uuid.UUID) -> dict[str, Any]:
    with conectar("aplicacion", base) as conn:
        fila = conn.execute(
            "SELECT estado, progreso, filas_leidas, filas_validas, filas_rechazadas, "
            "preparacion, latido FROM importacion WHERE id = %s",
            (importacion_id,),
        ).fetchone()
    assert fila is not None
    estado, progreso, leidas, validas, rechazadas, preparacion, latido = fila
    return {
        "estado": estado,
        "progreso": progreso,
        "filas_leidas": leidas,
        "filas_validas": validas,
        "filas_rechazadas": rechazadas,
        "preparacion": preparacion,
        "latido": latido,
    }


def _errores_db(conectar: Conectar, base: str, importacion_id: uuid.UUID) -> list[tuple[Any, ...]]:
    with conectar("aplicacion", base) as conn:
        return conn.execute(
            "SELECT hoja, fila, columna, tipo, mensaje, valor_original "
            "FROM importacion_error WHERE importacion_id = %s ORDER BY fila NULLS FIRST, columna",
            (importacion_id,),
        ).fetchall()


def _flujo_analisis(
    fabrica: sessionmaker[Session],
    importacion_id: uuid.UUID,
    contenido: bytes,
):
    from cimenta.presupuesto.aplicacion.analisis_importacion import (
        iniciar_analisis,
        registrar_resultado,
    )
    from cimenta.presupuesto.infraestructura.trabajo_analisis import analizar_contenido

    trabajo = iniciar_analisis(fabrica, importacion_id)
    resultado = analizar_contenido(contenido, trabajo.insumos_existentes)
    registrar_resultado(fabrica, importacion_id, resultado)
    return resultado


def test_hdu001_esc05_libro_valido_queda_validado(
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
    fabrica_sesiones: sessionmaker[Session],
    libro_catalogo: LibroCatalogo,
) -> None:
    """TC-24 · CA-1 — VALIDADO, preparación persistida, catálogos intactos."""
    antes = {t: _contar(conectar, base_de_prueba, t) for t in _TABLAS_SIN_CAMBIO}
    importacion_id = datos_presupuesto.importacion(estado="RECIBIDO")
    contenido = libro_sintetico(libro_catalogo, conceptos=20)
    resultado = _flujo_analisis(fabrica_sesiones, importacion_id, contenido)

    fila = _fila_importacion(conectar, base_de_prueba, importacion_id)
    assert fila["estado"] == "VALIDADO"
    assert fila["progreso"] == Decimal("1")
    assert _errores_db(conectar, base_de_prueba, importacion_id) == []
    assert resultado.preparacion["formato"] == FORMATO_PREPARACION
    assert fila["preparacion"]["formato"] == FORMATO_PREPARACION
    assert len(fila["preparacion"]["conceptos"]) == 20
    despues = {t: _contar(conectar, base_de_prueba, t) for t in _TABLAS_SIN_CAMBIO}
    assert antes == despues


def test_hdu001_esc06_ref_rota_seis_errores_y_197_en_preparacion(
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
    fabrica_sesiones: sessionmaker[Session],
    libro_catalogo: LibroCatalogo,
) -> None:
    """TC-25 · CA-2, CA-S1 — seis REF_ROTA y 197 conceptos en preparación."""
    _campos_rotos: tuple[CampoConcepto, ...] = ("precio_unitario", "importe")
    rotos: dict[tuple[int, CampoConcepto], str] = {
        (fila, campo): "#REF!" for fila in (20, 30, 40) for campo in _campos_rotos
    }
    importacion_id = datos_presupuesto.importacion(estado="RECIBIDO")
    _flujo_analisis(
        fabrica_sesiones,
        importacion_id,
        libro_sintetico(libro_catalogo, rotos=rotos),
    )
    fila = _fila_importacion(conectar, base_de_prueba, importacion_id)
    assert fila["estado"] == "CON_ERRORES"
    assert fila["filas_leidas"] == 200
    assert fila["filas_validas"] == 197
    assert fila["filas_rechazadas"] == 3
    errores = _errores_db(conectar, base_de_prueba, importacion_id)
    assert len(errores) == 6
    assert all(e[3] == "REF_ROTA" for e in errores)
    assert all(e[5] == "#REF!" for e in errores)
    prep_filas = {c["fila"] for c in fila["preparacion"]["conceptos"]}
    assert len(prep_filas) == 197
    assert prep_filas.isdisjoint({20, 30, 40})


def test_hdu001_esc07_sin_apu_persistido(
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
    fabrica_sesiones: sessionmaker[Session],
    libro_catalogo: LibroCatalogo,
) -> None:
    """TC-26 · CA-4 — SIN_APU del tercer código."""
    importacion_id = datos_presupuesto.importacion(estado="RECIBIDO")
    contenido = libro_sintetico(
        libro_catalogo,
        conceptos=3,
        codigos=("P-001", "P-002", "P-003"),
        hojas_apu=("P-001", "P-002"),
    )
    _flujo_analisis(fabrica_sesiones, importacion_id, contenido)
    errores = _errores_db(conectar, base_de_prueba, importacion_id)
    sin_apu = [e for e in errores if e[3] == "SIN_APU"]
    assert len(sin_apu) == 1
    assert sin_apu[0][5] == "P-003"
    assert sin_apu[0][4] == (
        "El concepto con código «P-003» no tiene hoja de análisis de precio unitario. "
        "Sin ese análisis no se puede calcular la explosión de insumos de ese concepto."
    )


def test_hdu001_esc08_unidad_desconocida_persistida(
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
    fabrica_sesiones: sessionmaker[Session],
    libro_catalogo: LibroCatalogo,
) -> None:
    """TC-27 · CA-5 — UNIDAD_DESCONOCIDA en fila 57."""
    importacion_id = datos_presupuesto.importacion(estado="RECIBIDO")
    _flujo_analisis(
        fabrica_sesiones,
        importacion_id,
        libro_sintetico(libro_catalogo, unidad_en={57: "XYZ"}),
    )
    errores = _errores_db(conectar, base_de_prueba, importacion_id)
    unidad = [e for e in errores if e[3] == "UNIDAD_DESCONOCIDA"]
    assert len(unidad) == 1
    assert unidad[0][1] == 57
    assert unidad[0][2] == "C"


def test_hdu001_esc28_rendimiento_ausente_persistido(
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
    fabrica_sesiones: sessionmaker[Session],
    libro_catalogo: LibroCatalogo,
) -> None:
    """TC-28 · CA-6 — RENDIMIENTO_AUSENTE en columna F."""
    importacion_id = datos_presupuesto.importacion(estado="RECIBIDO")
    _flujo_analisis(
        fabrica_sesiones,
        importacion_id,
        libro_sintetico(
            libro_catalogo,
            conceptos=20,
            variantes_apu={"P-001": {"celdas_rotas": {(8, "F"): None}}},
        ),
    )
    errores = _errores_db(conectar, base_de_prueba, importacion_id)
    rend = [e for e in errores if e[3] == "RENDIMIENTO_AUSENTE"]
    assert len(rend) == 1
    assert rend[0][2] == "F"


def test_hdu001_esc09_duplicado_persistido(
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
    fabrica_sesiones: sessionmaker[Session],
    libro_catalogo: LibroCatalogo,
) -> None:
    """TC-29 · CA-7 — DUPLICADO en fila 12."""
    importacion_id = datos_presupuesto.importacion(estado="RECIBIDO")
    _flujo_analisis(
        fabrica_sesiones,
        importacion_id,
        libro_sintetico(
            libro_catalogo,
            codigo_en={12: "620001", 45: "620001", 90: "620001"},
            descripciones={12: "MURO STD", 45: "MURO STD", 90: "PLAFON"},
        ),
    )
    errores = _errores_db(conectar, base_de_prueba, importacion_id)
    dup = [e for e in errores if e[3] == "DUPLICADO"]
    assert len(dup) == 1
    assert dup[0][1] == 12
    assert dup[0][5] == "620001"
    assert "12, 45 y 90" in dup[0][4]


@pytest.mark.parametrize(
    "contenido_fn",
    [
        lambda libro: libro_sintetico(libro, conceptos=0),
        lambda libro: libro_sintetico(libro, catalogo_vacio=True),
    ],
    ids=["solo_encabezados", "catalogo_vacio"],
)
def test_hdu001_esc27_sin_conceptos_persistido(
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
    fabrica_sesiones: sessionmaker[Session],
    libro_catalogo: LibroCatalogo,
    contenido_fn,
) -> None:
    """TC-30 · CA-9 — SIN_CONCEPTOS sin excepción."""
    importacion_id = datos_presupuesto.importacion(estado="RECIBIDO")
    _flujo_analisis(fabrica_sesiones, importacion_id, contenido_fn(libro_catalogo))
    fila = _fila_importacion(conectar, base_de_prueba, importacion_id)
    assert fila["estado"] == "CON_ERRORES"
    errores = _errores_db(conectar, base_de_prueba, importacion_id)
    sin_c = [e for e in errores if e[3] == "SIN_CONCEPTOS"]
    assert len(sin_c) == 1
    assert sin_c[0][0] is not None
    assert sin_c[0][1] is None and sin_c[0][2] is None


def test_hdu001_esc06_preparacion_con_dinero_en_cadena_sin_reabrir(
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
    fabrica_sesiones: sessionmaker[Session],
    libro_catalogo: LibroCatalogo,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """TC-31 · CA-11 esc. 1 — obtener_preparacion no reabre el Excel."""
    import cimenta.presupuesto.infraestructura.lector_catalogo as lector_mod
    from cimenta.presupuesto.aplicacion.analisis_importacion import obtener_preparacion

    importacion_id = datos_presupuesto.importacion(estado="RECIBIDO")
    _flujo_analisis(
        fabrica_sesiones,
        importacion_id,
        libro_sintetico(libro_catalogo, conceptos=20),
    )

    def _falla(*_args, **_kwargs):
        raise OSError("no debe abrirse el libro")

    monkeypatch.setattr(lector_mod, "load_workbook", _falla)
    prep = obtener_preparacion(fabrica_sesiones, importacion_id)
    assert prep is not None
    assert prep["formato"] == FORMATO_PREPARACION

    def _todas_cadenas(obj: object) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in ("cantidad", "precio_unitario", "importe", "rendimiento", "costo_unitario"):
                    assert v is None or isinstance(v, str)
                _todas_cadenas(v)
        elif isinstance(obj, list):
            for v in obj:
                _todas_cadenas(v)

    _todas_cadenas(prep)


def test_hdu001_esc29_interrupcion_no_deja_preparacion(
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
    fabrica_sesiones: sessionmaker[Session],
) -> None:
    """TC-32 · CA-11 esc. 2 — interrupción sin preparación."""
    from cimenta.presupuesto.aplicacion.analisis_importacion import (
        iniciar_analisis,
        registrar_interrupcion,
    )

    importacion_id = datos_presupuesto.importacion(estado="RECIBIDO")
    iniciar_analisis(fabrica_sesiones, importacion_id)
    assert registrar_interrupcion(fabrica_sesiones, importacion_id, MotivoInterrupcion.EXCEPCION)
    fila = _fila_importacion(conectar, base_de_prueba, importacion_id)
    assert fila["estado"] == "CON_ERRORES"
    assert fila["preparacion"] is None
    errores = _errores_db(conectar, base_de_prueba, importacion_id)
    assert len(errores) == 1
    assert errores[0][3] == "PROCESO_INTERRUMPIDO"
    assert errores[0][4] == error_de_interrupcion(MotivoInterrupcion.EXCEPCION).mensaje


@pytest.mark.parametrize(
    "estado_inicial, tipos_extra",
    [
        ("ANALIZANDO", ()),
        ("VALIDADO", ()),
        ("CONFIRMADO", ()),
        ("DESCARTADO", ()),
        ("CON_ERRORES", ("REF_ROTA",)),
    ],
)
def test_tkt015_estado_que_no_admite_analisis(
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
    fabrica_sesiones: sessionmaker[Session],
    estado_inicial: str,
    tipos_extra: tuple[str, ...],
) -> None:
    """TC-33 · CA-18 esc. 1 — ConflictoEstado ESTADO_NO_PERMITE_OPERACION."""
    from cimenta.presupuesto.aplicacion.analisis_importacion import iniciar_analisis

    importacion_id = datos_presupuesto.importacion(estado=estado_inicial)
    for tipo in tipos_extra:
        datos_presupuesto.error_importacion(importacion_id=importacion_id, tipo=tipo)
    antes = _fila_importacion(conectar, base_de_prueba, importacion_id)
    n_errores_antes = len(_errores_db(conectar, base_de_prueba, importacion_id))

    with pytest.raises(ConflictoEstado) as rechazo:
        iniciar_analisis(fabrica_sesiones, importacion_id)
    exc = rechazo.value
    assert exc.tipo == "CONFLICTO"
    assert exc.codigo.value == "ESTADO_NO_PERMITE_OPERACION"
    assert exc.detalle == {
        "importacion_id": str(importacion_id),
        "estado": estado_inicial,
    }
    assert exc.acciones == ()
    despues = _fila_importacion(conectar, base_de_prueba, importacion_id)
    assert despues["estado"] == antes["estado"]
    assert len(_errores_db(conectar, base_de_prueba, importacion_id)) == n_errores_antes


def test_hdu001_esc29_reintento_tras_interrupcion(
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
    fabrica_sesiones: sessionmaker[Session],
    libro_catalogo: LibroCatalogo,
) -> None:
    """TC-34 · CA-18 esc. 2 — reintento borra errores viejos."""
    from cimenta.presupuesto.aplicacion.analisis_importacion import (
        iniciar_analisis,
        registrar_interrupcion,
    )

    importacion_id = datos_presupuesto.importacion(estado="RECIBIDO")
    iniciar_analisis(fabrica_sesiones, importacion_id)
    registrar_interrupcion(fabrica_sesiones, importacion_id, MotivoInterrupcion.REINICIO)
    assert len(_errores_db(conectar, base_de_prueba, importacion_id)) == 1

    trabajo = iniciar_analisis(fabrica_sesiones, importacion_id)
    fila = _fila_importacion(conectar, base_de_prueba, importacion_id)
    assert fila["estado"] == "ANALIZANDO"
    assert fila["progreso"] == Decimal("0")
    assert fila["latido"] is not None
    assert fila["preparacion"] is None
    assert _errores_db(conectar, base_de_prueba, importacion_id) == []

    from cimenta.presupuesto.aplicacion.analisis_importacion import registrar_resultado
    from cimenta.presupuesto.infraestructura.trabajo_analisis import analizar_contenido

    contenido = libro_sintetico(libro_catalogo, conceptos=20)
    resultado = analizar_contenido(contenido, trabajo.insumos_existentes)
    registrar_resultado(fabrica_sesiones, importacion_id, resultado)
    assert _fila_importacion(conectar, base_de_prueba, importacion_id)["estado"] == "VALIDADO"
    assert len(_errores_db(conectar, base_de_prueba, importacion_id)) == 0


def test_tkt015_dos_solicitudes_simultaneas(
    base_de_prueba: str,
    datos_presupuesto: DatosPresupuesto,
    motor_aplicacion,
) -> None:
    """TC-35 · CA-18 esc. 3 — un TrabajoAnalisis y un ConflictoEstado ANALIZANDO."""
    from cimenta.presupuesto.aplicacion.analisis_importacion import iniciar_analisis
    from cimenta.presupuesto.dominio.importacion import TrabajoAnalisis
    from cimenta.presupuesto.infraestructura import repositorio_importacion as repositorio

    importacion_id = datos_presupuesto.importacion(estado="RECIBIDO")
    fabrica_a = sessionmaker(bind=motor_aplicacion, expire_on_commit=False)
    fabrica_b = sessionmaker(bind=motor_aplicacion, expire_on_commit=False)
    barrera = threading.Barrier(2)
    resultados: list[object] = [None, None]
    pasar_original = repositorio.pasar_a_analizando

    def _pasar_con_retardo(sesion_bd: Session, imp_id: uuid.UUID) -> None:
        time.sleep(0.4)
        pasar_original(sesion_bd, imp_id)

    def _worker(indice: int, fabrica: sessionmaker[Session]) -> None:
        barrera.wait()
        try:
            resultados[indice] = iniciar_analisis(fabrica, importacion_id)
        except ConflictoEstado as conflicto:
            resultados[indice] = conflicto

    hilos = [
        threading.Thread(target=_worker, args=(0, fabrica_a)),
        threading.Thread(target=_worker, args=(1, fabrica_b)),
    ]
    with patch.object(repositorio, "pasar_a_analizando", side_effect=_pasar_con_retardo):
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join(timeout=30)
            assert not hilo.is_alive()

    trabajos = [r for r in resultados if isinstance(r, TrabajoAnalisis)]
    conflictos = [r for r in resultados if isinstance(r, ConflictoEstado)]
    assert len(trabajos) == 1
    assert len(conflictos) == 1
    assert conflictos[0].detalle["estado"] == "ANALIZANDO"


def test_tkt015_importacion_inexistente(fabrica_sesiones: sessionmaker[Session]) -> None:
    """TC-36 · CA-18 — NoEncontrado."""
    from cimenta.presupuesto.aplicacion.analisis_importacion import iniciar_analisis

    with pytest.raises(NoEncontrado) as rechazo:
        iniciar_analisis(fabrica_sesiones, uuid.uuid4())
    assert rechazo.value.recurso == "importacion"


def test_tkt015_resultado_tardio_no_pisa_el_estado(
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
    fabrica_sesiones: sessionmaker[Session],
    libro_catalogo: LibroCatalogo,
) -> None:
    """TC-37 · CA-16 — registrar_resultado descartado."""
    from cimenta.presupuesto.aplicacion.analisis_importacion import (
        iniciar_analisis,
        registrar_resultado,
    )
    from cimenta.presupuesto.infraestructura.trabajo_analisis import analizar_contenido

    importacion_id = datos_presupuesto.importacion(estado="RECIBIDO")
    trabajo = iniciar_analisis(fabrica_sesiones, importacion_id)
    resultado = analizar_contenido(
        libro_sintetico(libro_catalogo, conceptos=20),
        trabajo.insumos_existentes,
    )
    with conectar("aplicacion", base_de_prueba) as conn:
        conn.execute(
            "UPDATE importacion SET estado = 'CON_ERRORES' WHERE id = %s",
            (importacion_id,),
        )
    assert registrar_resultado(fabrica_sesiones, importacion_id, resultado) is False
    fila = _fila_importacion(conectar, base_de_prueba, importacion_id)
    assert fila["estado"] == "CON_ERRORES"
    assert fila["preparacion"] is None


def test_tkt015_errores_en_lote_todo_o_nada(
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
    fabrica_sesiones: sessionmaker[Session],
) -> None:
    """TC-38 · CA-3 — lote atómico; CHECK rechaza tipo inválido."""
    from cimenta.presupuesto.aplicacion.analisis_importacion import (
        iniciar_analisis,
        registrar_resultado,
    )
    from cimenta.presupuesto.infraestructura.trabajo_analisis import ResultadoAnalisis

    importacion_id = datos_presupuesto.importacion(estado="RECIBIDO")
    iniciar_analisis(fabrica_sesiones, importacion_id)

    base_error = ErrorImportacion(
        tipo=TipoErrorImportacion.REF_ROTA,
        hoja="CATALOGO",
        fila=10,
        columna="F",
        mensaje="x",
        valor_original="#REF!",
    )
    validos = tuple(
        ErrorImportacion(
            tipo=base_error.tipo,
            hoja=base_error.hoja,
            fila=10 + (i % 50),
            columna=base_error.columna,
            mensaje=f"m{i}",
            valor_original=base_error.valor_original,
        )
        for i in range(8600)
    )
    prep_min = {
        "formato": 1,
        "conceptos": [],
        "nodos": [],
        "analisis": [],
        "asociaciones": [],
        "insumos_por_crear": [],
    }
    ok = registrar_resultado(
        fabrica_sesiones,
        importacion_id,
        ResultadoAnalisis(
            errores=validos,
            preparacion=prep_min,
            filas_leidas=8600,
            filas_validas=0,
            filas_rechazadas=8600,
        ),
    )
    assert ok is True
    assert len(_errores_db(conectar, base_de_prueba, importacion_id)) == 8600

    importacion_id = datos_presupuesto.importacion(estado="RECIBIDO")
    iniciar_analisis(fabrica_sesiones, importacion_id)
    malo = ErrorImportacion(
        tipo=TipoErrorImportacion.REF_ROTA,
        hoja="C",
        fila=1,
        columna="A",
        mensaje="m",
        valor_original="x",
    )
    object.__setattr__(malo, "tipo", "TIPO_INVALIDO")
    from sqlalchemy.exc import DBAPIError

    with pytest.raises(DBAPIError):
        registrar_resultado(
            fabrica_sesiones,
            importacion_id,
            ResultadoAnalisis(
                errores=(*validos[:100], malo),
                preparacion=prep_min,
                filas_leidas=101,
                filas_validas=0,
                filas_rechazadas=101,
            ),
        )
    fila = _fila_importacion(conectar, base_de_prueba, importacion_id)
    assert fila["estado"] == "ANALIZANDO"
    assert fila["preparacion"] is None
    assert len(_errores_db(conectar, base_de_prueba, importacion_id)) == 0


def _error_sin_apu() -> ErrorImportacion:
    catalogo = CatalogoLeido(
        hoja="C",
        fila_encabezado=4,
        nodos=(),
        conceptos=(
            ConceptoLeido(
                fila=30,
                codigo="P-003",
                descripcion=None,
                unidad="M2",
                cantidad=None,
                precio_unitario=None,
                importe=None,
                ruta=Ruta(None, None, None, None),
            ),
        ),
        hallazgos=(),
    )
    return errores_sin_apu(catalogo, ("P-003",))[0]


_ERRORES_TC39: list[ErrorImportacion] = [
    *[clasificar_hallazgo(hallazgo_ejemplo(c)) for c in TIPO_POR_CAUSA],
    _error_sin_apu(),
    detectar_duplicados(
        catalogo_con_descripciones([(12, "620001", "MURO STD"), (45, "620001", "PLAFON")])
    )[0],
    error_de_interrupcion(MotivoInterrupcion.REINICIO),
]
_IDS_TC39 = [c.value for c in TIPO_POR_CAUSA] + ["SIN_APU", "DUPLICADO", "PROCESO_INTERRUMPIDO"]


@pytest.mark.parametrize("error", _ERRORES_TC39, ids=_IDS_TC39)
def test_hdu001_esc06_cada_tipo_y_causa_persisten(
    base_de_prueba: str,
    conectar: Conectar,
    datos_presupuesto: DatosPresupuesto,
    fabrica_sesiones: sessionmaker[Session],
    error: ErrorImportacion,
) -> None:
    """TC-39 · CA-10 — insertar_errores conserva cada campo."""
    from cimenta.presupuesto.infraestructura import repositorio_importacion as repo

    importacion_id = datos_presupuesto.importacion(estado="RECIBIDO")
    with fabrica_sesiones.begin() as sesion:
        repo.insertar_errores(sesion, importacion_id, (error,))
    filas = _errores_db(conectar, base_de_prueba, importacion_id)
    assert len(filas) == 1
    hoja, fila, columna, tipo, mensaje, valor = filas[0]
    assert tipo == str(error.tipo)
    assert mensaje == error.mensaje
    assert valor == error.valor_original
    assert hoja == error.hoja
    assert fila == error.fila
    assert columna == error.columna
