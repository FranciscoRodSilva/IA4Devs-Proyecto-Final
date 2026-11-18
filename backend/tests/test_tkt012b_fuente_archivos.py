"""La fuente de historial de `archivos` (TKT-012b, ciclo de corrección de la auditoría de cierre, hallazgo F001).

`archivo.obra_id` es `NOT NULL` y **no** tiene clave foránea hacia `obra` (migración `0012`): el motor no
protege a una obra con archivos. Sin una fuente de historial, `DELETE /api/v1/obras/{id}` borraba la obra
y dejaba huérfanas las filas y los objetos del almacén. El ADR
`docs/adr/20261117-historial-de-obra-por-puerto-inyectado.md` obliga al primer módulo que escribe filas con
`obra_id` a publicar su `FuenteHistorialObra`; `archivos` ya existía y no lo hizo.

Contrato que esta fila fija (el desarrollador lo implementa, no lo discute):

- `cimenta.archivos.interfaz.FuenteHistorialArchivos`: clase sin argumentos de construcción, con
  `nombre == "archivos"` y `contar(sesion_bd, obra_id) -> int` (la firma del puerto
  `FuenteHistorialObra`). Se publica en `__all__` de `interfaz.py`. `archivos` **no** importa `presupuesto`:
  el puerto es estructural (`Protocol`).
- `contar` cuenta **todas** las filas de `archivo` de la obra, en cualquier estado (`PENDIENTE`,
  `DISPONIBLE`, `CADUCADO`, `ANULADO`). `(asumido)`: un adjunto se anula con motivo y nunca se borra (regla
  15 de CLAUDE.md, ADR-016), así que un archivo `ANULADO` sigue siendo una fila que colgaría huérfana, y un
  `PENDIENTE` o `CADUCADO` también es fila y objeto potencial en el almacén. Si la persona dueña decide que
  los `CADUCADO` no cuentan, cambia solo `ESTADOS_DE_ARCHIVO` y el parámetro de `..._cuenta_el_estado`.
- Usa la sesión del llamador: ve lo que esa transacción ve, no confirma y no abre otra conexión.
- `servidor/fabrica.py` la pasa en `fuentes_historial` a `montar_presupuesto`, importándola solo de
  `cimenta.archivos.interfaz`.

Rojo esperado de la fila (esqueleto de `contar` con `NotImplementedError`, fábrica sin cablear): las pruebas
de la fuente fallan con `NotImplementedError`; el rechazo por HTTP recibe `204` en lugar de `409` porque la
fábrica no pasa la fuente y la obra se borra; la prueba de composición ve `fuentes_historial == ()`. Nacen
en verde, a propósito: el `nombre`, la firma, la no importación cruzada, `lint-imports` y las dos pruebas
del borrado sin archivos (el contrapeso del rechazo: que la fuente no bloquee lo que no tiene historial).

Mutantes que esta fila pone en rojo: no filtrar por `obra_id`; contar solo `DISPONIBLE` o excluir los
`ANULADO`; abrir otra sesión (no ve la transacción del llamador); confirmar la sesión; devolver un `bool`
o un `Row`; no cablear la fuente en la fábrica; importarla de un submódulo en lugar de la interfaz.
"""

# Las fixtures importadas por nombre (`abrir_sesion`, `base`) se piden como parámetro: Ruff lo lee como F811.
# ruff: noqa: F811

from __future__ import annotations

import ast
import inspect
import os
import re
import subprocess
import sys
import uuid
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from cimenta.archivos import interfaz
from cimenta.archivos.dominio.confirmacion import EstadoArchivo
from cimenta.archivos.infraestructura.repositorio import FilaArchivo, insertar
from cimenta.archivos.interfaz import FuenteHistorialArchivos
from herramientas.soporte_tkt017_api import (
    TOKEN_CSRF,
    Sesion,
    abrir_sesion,  # noqa: F401
    base,  # noqa: F401
    cabeceras_de,
    construir_aplicacion,
    exigir_error,
)
from herramientas.soporte_tkt017_entorno import Base

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta.
    from conftest import DatosPresupuesto, RelojDePrueba

BACKEND = Path(__file__).resolve().parents[1]
RUTA = "/api/v1/obras"
CODIGO = "AP-058-25"
MENSAJE_CON_HISTORIAL = "La obra {codigo} tiene historial y no se puede eliminar."
ESTADOS_DE_ARCHIVO = ["PENDIENTE", "DISPONIBLE", "CADUCADO", "ANULADO"]
HASH = "a" * 64
ENTORNO = {**os.environ, "PYTHONIOENCODING": "utf-8", "COLUMNS": "250"}
# `import-linter` no tiene `__main__`: se invoca el mismo punto de entrada que `lint-imports`.
LINTER = "from importlinter.cli import lint_imports_command; lint_imports_command()"
RESUMEN = re.compile(r"Contracts: (\d+) kept, (\d+) broken")


# --------------------------------------------------------------------------- ayudas de la prueba


def _registrar_archivo(
    base: Base,
    obra_id: uuid.UUID,
    subido_por_id: uuid.UUID,
    estado: str,
    momento: datetime,
) -> uuid.UUID:
    """Una fila de `archivo` de la obra en el estado pedido, con SQL directo del rol de aplicación.

    Cumple los `CHECK` de la migración `0012`: un `DISPONIBLE` trae hash, tamaño y confirmación; un
    `ANULADO`, quién lo anuló y el motivo. La clave del objeto es única por fila.
    """
    archivo_id = uuid.uuid4()
    disponible = estado == "DISPONIBLE"
    anulado = estado == "ANULADO"
    base.ejecutar(
        "INSERT INTO archivo (id, obra_id, referencia_tipo, referencia_id, estado, clave_objeto, "
        "nombre_original, tipo_mime, tamano_bytes, hash_sha256, subido_por_id, creado_en, "
        "confirmado_en, anulado_por_id, motivo_anulacion, anulado_en) "
        "VALUES (%s, %s, 'OBRA', NULL, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        archivo_id,
        obra_id,
        estado,
        f"obras/{obra_id}/{archivo_id}",
        "plano.png",
        "image/png" if disponible else None,
        1024 if disponible else None,
        HASH if disponible else None,
        subido_por_id,
        momento,
        momento if disponible else None,
        subido_por_id if anulado else None,
        "Archivo equivocado" if anulado else None,
        momento if anulado else None,
    )
    return archivo_id


def _cuenta(base: Base, consulta: Any, *parametros: object) -> int:
    fila = base.conexion.execute(consulta, parametros).fetchone()
    assert fila is not None
    return int(fila[0])


@pytest.fixture
def empresa_de_la_migracion(base: Base) -> uuid.UUID:
    """La única empresa activa de la base migrada (`0008`): la que toma el alta."""
    filas = base.filas("SELECT id FROM empresa WHERE activa")
    assert len(filas) == 1, f"La migración debe dejar una empresa activa y deja {len(filas)}"
    return uuid.UUID(str(filas[0][0]))


@pytest.fixture
def usuario_id(datos_presupuesto: DatosPresupuesto) -> uuid.UUID:
    """Quien sube los archivos sembrados (la clave foránea de `archivo.subido_por_id` lo exige)."""
    return datos_presupuesto.usuario()


@pytest.fixture
def fabricar_obra(
    datos_presupuesto: DatosPresupuesto, empresa_de_la_migracion: uuid.UUID
) -> Callable[..., uuid.UUID]:
    """Una obra sin línea base ni importaciones, en el estado pedido (por omisión, `PLANEACION`)."""
    creador = datos_presupuesto.usuario()

    def fabricar(*, codigo: str = CODIGO, estado: str = "PLANEACION") -> uuid.UUID:
        return datos_presupuesto.obra(
            codigo=codigo, empresa_id=empresa_de_la_migracion, creado_por_id=creador, estado=estado
        )

    return fabricar


@pytest.fixture
def sesion_bd(motor_aplicacion: Engine) -> Any:
    """Una sesión del rol de aplicación sobre la base de la prueba; se cierra (y deshace) al terminar."""
    with Session(motor_aplicacion) as sesion:
        yield sesion


def _borrar(cliente: TestClient, sesion: Sesion, obra_id: object) -> Any:
    """`DELETE /api/v1/obras/{id}` con la cookie de sesión y el par CSRF válido."""
    return cliente.request(
        "DELETE",
        f"{RUTA}/{obra_id}",
        headers=cabeceras_de(sesion.sesion_id, TOKEN_CSRF, TOKEN_CSRF),
    )


def _foto(base: Base) -> dict[str, object]:
    """Lo que un rechazo no debe cambiar: obras, archivos y bitácora (sin los `DENEGAR`)."""
    return {
        "obras": base.filas("SELECT * FROM obra ORDER BY id"),
        "archivos": base.filas("SELECT * FROM archivo ORDER BY id"),
        "asientos": base.filas(
            "SELECT id, accion::text, entidad_id FROM bitacora WHERE accion <> 'DENEGAR' ORDER BY id"
        ),
    }


def _exigir_con_historial(
    respuesta: Any, obra_id: uuid.UUID, *, estado: str, detalle: dict[str, object]
) -> None:
    """El `409` `CONFLICTO` `OBRA_CON_HISTORIAL` completo: nunca `REGLA_NEGOCIO`, con las acciones del estado."""
    acciones_por_estado = {"PLANEACION": [("CERRAR_OBRA", "cierre")], "CERRADA": []}
    assert respuesta.status_code == 409, (
        f"La obra con historial debía responder 409 y responde {respuesta.status_code}: "
        "si es 204, se borró con archivos que quedan huérfanos"
    )
    cuerpo = exigir_error(
        respuesta,
        estado=409,
        esperado={
            "tipo": "CONFLICTO",
            "codigo": "OBRA_CON_HISTORIAL",
            "mensaje": MENSAJE_CON_HISTORIAL.format(codigo=CODIGO),
            "detalle": detalle,
            "acciones": [
                {"clave": clave, "metodo": "POST", "ruta": f"{RUTA}/{obra_id}/{segmento}"}
                for clave, segmento in acciones_por_estado[estado]
            ],
        },
        esquema="ErrorConflictoEstado",
    )
    assert "regla" not in cuerpo


def _detalle(
    *, congelada: bool = False, lineas_base: int = 0, importaciones: int = 0, movimientos: int = 0
) -> dict[str, object]:
    return {
        "linea_base_congelada": congelada,
        "lineas_base": lineas_base,
        "importaciones": importaciones,
        "movimientos": movimientos,
    }


# --------------------------------------------------------------------------- F001 · la fuente, contra PostgreSQL


def test_tkt012b_f001_la_fuente_se_llama_archivos_y_cumple_la_firma_del_puerto() -> None:
    """F001 · ADR del puerto — `nombre == "archivos"` y `contar(sesion_bd, obra_id)`, como `FuenteHistorialObra`.

    Nace en verde (el esqueleto ya trae el nombre y la firma): fija el contrato que el puerto lee.
    """
    fuente = FuenteHistorialArchivos()

    assert fuente.nombre == "archivos"
    assert list(inspect.signature(fuente.contar).parameters) == ["sesion_bd", "obra_id"]


def test_tkt012b_f001_una_obra_sin_archivos_cuenta_cero(
    sesion_bd: Session, fabricar_obra: Callable[..., uuid.UUID]
) -> None:
    """F001 · RN-01 — sin filas en `archivo`, la fuente cuenta `0` (y no es `None` ni falla)."""
    obra_id = fabricar_obra()

    cuenta = FuenteHistorialArchivos().contar(sesion_bd, obra_id)

    assert cuenta == 0
    assert type(cuenta) is int


@pytest.mark.parametrize("estado", ESTADOS_DE_ARCHIVO)
def test_tkt012b_f001_la_fuente_cuenta_el_estado(
    estado: str,
    base: Base,
    sesion_bd: Session,
    fabricar_obra: Callable[..., uuid.UUID],
    usuario_id: uuid.UUID,
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """F001 · RN-01 · ADR-016 — un archivo en cualquier estado cuenta, también el `ANULADO` `(asumido)`.

    Un adjunto se anula con motivo y nunca se borra: la fila anulada sigue existiendo y sigue colgando
    de la obra sin clave foránea que la detenga. Contar solo los `DISPONIBLE` deja huérfano el resto.
    """
    obra_id = fabricar_obra()
    _registrar_archivo(base, obra_id, usuario_id, estado, reloj_de_prueba.ahora)

    cuenta = FuenteHistorialArchivos().contar(sesion_bd, obra_id)

    assert cuenta == 1, f"Un archivo {estado} es historial de la obra y debe contarse"
    assert type(cuenta) is int


def test_tkt012b_f001_la_fuente_cuenta_n_archivos_y_solo_los_de_su_obra(
    base: Base,
    sesion_bd: Session,
    fabricar_obra: Callable[..., uuid.UUID],
    usuario_id: uuid.UUID,
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """F001 · RN-01 — `N` archivos de la obra cuentan `N`; los de otra obra no suman, y una tercera vale `0`.

    Obra A con los cuatro estados (4), obra B con tres `DISPONIBLE` (3) y obra C vacía (0): un conteo
    sin `WHERE obra_id` daría 7 para las tres, y uno que cuente por obra equivocada mezclaría A y B.
    """
    obra_a = fabricar_obra(codigo="AP-001-26")
    obra_b = fabricar_obra(codigo="AP-002-26")
    obra_c = fabricar_obra(codigo="AP-003-26")
    for estado in ESTADOS_DE_ARCHIVO:
        _registrar_archivo(base, obra_a, usuario_id, estado, reloj_de_prueba.ahora)
    for _ in range(3):
        _registrar_archivo(base, obra_b, usuario_id, "DISPONIBLE", reloj_de_prueba.ahora)
    fuente = FuenteHistorialArchivos()

    assert fuente.contar(sesion_bd, obra_a) == 4
    assert fuente.contar(sesion_bd, obra_b) == 3
    assert fuente.contar(sesion_bd, obra_c) == 0
    assert fuente.contar(sesion_bd, uuid.uuid4()) == 0


def test_tkt012b_f001_la_fuente_usa_la_transaccion_del_llamador_y_no_confirma(
    base: Base,
    sesion_bd: Session,
    fabricar_obra: Callable[..., uuid.UUID],
    usuario_id: uuid.UUID,
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """F001 · ADR del puerto — el conteo ve lo no confirmado de la sesión del llamador y no la confirma.

    El caso de uso `eliminar_obra` cuenta dentro de la transacción que ya tiene la obra bloqueada, para que
    conteo y borrado vean el mismo estado. Se inserta un archivo con la propia sesión, sin confirmar: una
    fuente que abriera otra conexión contaría `0`; una que confirmara dejaría la fila visible para otros.
    """
    obra_id = fabricar_obra()
    insertar(
        sesion_bd,
        FilaArchivo(
            id=uuid.uuid4(),
            obra_id=obra_id,
            referencia_tipo="OBRA",
            referencia_id=None,
            estado=EstadoArchivo.PENDIENTE,
            clave_objeto=f"obras/{obra_id}/sin-confirmar",
            nombre_original="plano.png",
            tipo_mime=None,
            tamano_bytes=None,
            hash_sha256=None,
            subido_por_id=usuario_id,
            creado_en=reloj_de_prueba.ahora,
            confirmado_en=None,
            anulado_por_id=None,
            motivo_anulacion=None,
            anulado_en=None,
        ),
    )

    cuenta = FuenteHistorialArchivos().contar(sesion_bd, obra_id)

    assert cuenta == 1, (
        "La fuente debe leer con la sesión del llamador, donde la fila aún no se confirma"
    )
    assert sesion_bd.in_transaction(), (
        "La fuente no debe cerrar ni confirmar la transacción del llamador"
    )
    assert _cuenta(base, "SELECT count(*) FROM archivo WHERE obra_id = %s", obra_id) == 0, (
        "Nada se confirmó: otra conexión no ve la fila"
    )


# --------------------------------------------------------------------------- F001 · de extremo a extremo por HTTP


@pytest.mark.parametrize(
    ("estados", "movimientos"),
    [
        pytest.param(["PENDIENTE"], 1, id="un_pendiente"),
        pytest.param(["DISPONIBLE"], 1, id="un_disponible"),
        pytest.param(["ANULADO"], 1, id="solo_un_anulado"),
        pytest.param(ESTADOS_DE_ARCHIVO, 4, id="los_cuatro_estados"),
    ],
)
def test_hdu001_esc20_api_delete_de_obra_con_archivos_responde_409_y_no_la_borra(
    estados: list[str],
    movimientos: int,
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    fabricar_obra: Callable[..., uuid.UUID],
    usuario_id: uuid.UUID,
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """HDU-001 esc. 20 · F001 · RN-01 — con archivos registrados: `409` `OBRA_CON_HISTORIAL` con el conteo en `movimientos`.

    La aplicación es la compuesta por la fábrica real (`crear_aplicacion`): la prueba falla si la fábrica
    no inyecta la fuente. La obra está en `PLANEACION` y sin línea base ni importaciones, así que lo único
    que le da historial son los archivos: `movimientos` es el número de filas de `archivo` de esa obra,
    de los cuatro estados (el `ANULADO` también cuenta). El detalle trae las cifras exactas, las acciones
    son las del estado (`CERRAR_OBRA`) y nada cambia: la obra, sus archivos y la bitácora quedan intactos.
    """
    sesion = abrir_sesion()
    obra_id = fabricar_obra()
    otra = fabricar_obra(codigo="AP-777-26")
    for estado in estados:
        _registrar_archivo(base, obra_id, usuario_id, estado, reloj_de_prueba.ahora)
    _registrar_archivo(base, otra, usuario_id, "DISPONIBLE", reloj_de_prueba.ahora)
    antes = _foto(base)

    respuesta = _borrar(cliente, sesion, obra_id)

    _exigir_con_historial(
        respuesta, obra_id, estado="PLANEACION", detalle=_detalle(movimientos=movimientos)
    )
    assert _foto(base) == antes
    assert _cuenta(base, "SELECT count(*) FROM obra WHERE id = %s", obra_id) == 1
    assert _cuenta(base, "SELECT count(*) FROM archivo WHERE obra_id = %s", obra_id) == len(estados)
    assert _cuenta(base, "SELECT count(*) FROM bitacora WHERE accion = 'ELIMINAR'") == 0


def test_hdu001_esc20_api_delete_suma_los_archivos_al_historial_propio(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    fabricar_obra: Callable[..., uuid.UUID],
    datos_presupuesto: DatosPresupuesto,
    usuario_id: uuid.UUID,
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """HDU-001 esc. 20 · F001 · RN-01 — una línea base borrador y dos archivos: `lineas_base` 1 y `movimientos` 2.

    El conteo de la fuente se suma en `movimientos` y no pisa ni se mezcla con el historial propio de
    `presupuesto`: cada cifra del detalle es la suya.
    """
    sesion = abrir_sesion()
    obra_id = fabricar_obra()
    datos_presupuesto.linea_base(estado="BORRADOR", obra_id=obra_id)
    _registrar_archivo(base, obra_id, usuario_id, "DISPONIBLE", reloj_de_prueba.ahora)
    _registrar_archivo(base, obra_id, usuario_id, "ANULADO", reloj_de_prueba.ahora)

    respuesta = _borrar(cliente, sesion, obra_id)

    _exigir_con_historial(
        respuesta, obra_id, estado="PLANEACION", detalle=_detalle(lineas_base=1, movimientos=2)
    )


def test_hdu001_esc20_api_delete_de_obra_sin_archivos_pero_con_vecina_con_archivos_responde_204(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    fabricar_obra: Callable[..., uuid.UUID],
    usuario_id: uuid.UUID,
    reloj_de_prueba: RelojDePrueba,
) -> None:
    """HDU-001 esc. 20 · F001 · RN-01 — sin archivos propios, la obra se elimina aunque otra obra tenga archivos.

    Es el contrapeso del rechazo: la fuente cuenta por obra, y los archivos de una obra no impiden borrar
    otra. Se elimina solo la pedida, se asienta un único `ELIMINAR` con `RN-01` y los archivos de la
    vecina quedan intactos. Nace en verde: el borrado sin historial ya funciona.
    """
    sesion = abrir_sesion()
    obra_id = fabricar_obra()
    vecina = fabricar_obra(codigo="AP-777-26")
    _registrar_archivo(base, vecina, usuario_id, "DISPONIBLE", reloj_de_prueba.ahora)
    _registrar_archivo(base, vecina, usuario_id, "ANULADO", reloj_de_prueba.ahora)

    respuesta = _borrar(cliente, sesion, obra_id)

    assert respuesta.status_code == 204, respuesta.text
    assert respuesta.content == b""
    assert _cuenta(base, "SELECT count(*) FROM obra WHERE id = %s", obra_id) == 0
    assert _cuenta(base, "SELECT count(*) FROM obra WHERE id = %s", vecina) == 1
    assert _cuenta(base, "SELECT count(*) FROM archivo WHERE obra_id = %s", vecina) == 2
    assert base.filas(
        "SELECT accion::text, entidad_id, regla_negocio FROM bitacora WHERE accion = 'ELIMINAR'"
    ) == [("ELIMINAR", obra_id, "RN-01")]


def test_hdu001_esc20_api_delete_de_obra_sin_archivos_responde_204(
    base: Base,
    cliente: TestClient,
    abrir_sesion: Callable[..., Sesion],
    fabricar_obra: Callable[..., uuid.UUID],
) -> None:
    """HDU-001 esc. 20 · F001 · RN-01 — una obra sin historial ni archivos se elimina: `204` sin cuerpo.

    Nace en verde: la corrección no debe bloquear lo que no tiene historial.
    """
    sesion = abrir_sesion()
    obra_id = fabricar_obra()

    respuesta = _borrar(cliente, sesion, obra_id)

    assert respuesta.status_code == 204, respuesta.text
    assert _cuenta(base, "SELECT count(*) FROM obra WHERE id = %s", obra_id) == 0


# --------------------------------------------------------------------------- F001 · composición y fronteras


def test_tkt012b_f001_la_fabrica_pasa_la_fuente_de_archivos_al_contexto_de_presupuesto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F001 · ADR del puerto — `crear_aplicacion` deja la fuente `archivos` en `app.state.presupuesto`.

    Sin Docker: es la raíz de composición. Con `fuentes_historial` vacío la fuente existe pero nadie la
    consulta, y la obra con archivos se borraría. La lista exacta evita que otra fuente se cuele sin ADR.
    """
    aplicacion = construir_aplicacion(monkeypatch)

    fuentes = aplicacion.state.presupuesto.fuentes_historial

    assert [fuente.nombre for fuente in fuentes] == ["archivos"]
    assert isinstance(fuentes[0], FuenteHistorialArchivos)


def _importaciones(ruta: Path) -> list[str]:
    """Los módulos que importa el archivo (`import x`, `from x import y`), por AST."""
    arbol = ast.parse(ruta.read_text(encoding="utf-8"))
    modulos: list[str] = []
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            modulos.extend(alias.name for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module is not None and nodo.level == 0:
            modulos.append(nodo.module)
    return modulos


def test_tkt012b_f001_archivos_publica_la_fuente_solo_por_su_interfaz() -> None:
    """F001 · regla 3 de CLAUDE.md — `FuenteHistorialArchivos` está en `__all__` de `cimenta.archivos.interfaz`.

    `servidor/fabrica.py` la importa de ahí y de ningún submódulo de `archivos`; además la clase vive en
    `archivos` (no se reexporta una de otro módulo).
    """
    assert "FuenteHistorialArchivos" in interfaz.__all__
    assert FuenteHistorialArchivos.__module__.startswith("cimenta.archivos.")
    arbol = ast.parse((BACKEND / "servidor" / "fabrica.py").read_text(encoding="utf-8"))
    de_donde = {
        nodo.module
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.ImportFrom)
        and nodo.module is not None
        and any(alias.name == "FuenteHistorialArchivos" for alias in nodo.names)
    }
    assert de_donde == {"cimenta.archivos.interfaz"}, (
        f"La fábrica debe importar la fuente solo de la interfaz de archivos y la importa de {de_donde}"
    )


def test_tkt012b_f001_la_fabrica_la_pasa_en_fuentes_historial_a_montar_presupuesto() -> None:
    """F001 · ADR del puerto — la llamada `montar_presupuesto(...)` de la fábrica lleva `fuentes_historial=`.

    Comprobación de AST, la misma que la de la fábrica real pero sin construir la aplicación: el
    argumento existe y menciona `FuenteHistorialArchivos`.
    """
    arbol = ast.parse((BACKEND / "servidor" / "fabrica.py").read_text(encoding="utf-8"))
    llamadas = [
        nodo
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.Call)
        and isinstance(nodo.func, ast.Name)
        and nodo.func.id == "montar_presupuesto"
    ]
    assert len(llamadas) == 1
    argumentos = {palabra.arg: palabra.value for palabra in llamadas[0].keywords}
    assert "fuentes_historial" in argumentos, "La fábrica no pasa `fuentes_historial` a presupuesto"
    nombres = {
        nodo.id for nodo in ast.walk(argumentos["fuentes_historial"]) if isinstance(nodo, ast.Name)
    }
    assert "FuenteHistorialArchivos" in nombres


def test_tkt012b_f001_presupuesto_no_importa_archivos_ni_archivos_a_presupuesto() -> None:
    """F001 · ADR del puerto — el puerto es estructural: ninguno de los dos módulos importa al otro.

    `presupuesto` no depende de ningún módulo de negocio y `archivos` no necesita su `Protocol` para
    cumplirlo. Se revisa por AST cada archivo de los dos paquetes (Ruff y `lint-imports` no ven una
    importación diferida dentro de una función; el AST sí).
    """
    for paquete, prohibido in (
        ("presupuesto", "cimenta.archivos"),
        ("archivos", "cimenta.presupuesto"),
    ):
        for ruta in sorted((BACKEND / "cimenta" / paquete).rglob("*.py")):
            cruzadas = [
                modulo
                for modulo in _importaciones(ruta)
                if modulo == prohibido or modulo.startswith(prohibido + ".")
            ]
            assert cruzadas == [], f"{ruta.relative_to(BACKEND)} importa {cruzadas}"


def test_tkt012b_f001_lint_imports_sigue_limpio() -> None:
    """F001 · regla 3 de CLAUDE.md — `lint-imports` cumple todos los contratos y ninguno se rompe.

    Se corre el verificador real sobre el árbol real, sin caché. Nace en verde: el esqueleto no cruza
    ninguna frontera; protege la implementación de la fase verde y de la fábrica.
    """
    proceso = subprocess.run(
        [sys.executable, "-c", LINTER, "--no-cache"],
        cwd=BACKEND,
        env=ENTORNO,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
        check=False,
    )
    salida = proceso.stdout + proceso.stderr
    resumen = RESUMEN.search(salida)
    assert resumen is not None, salida
    assert proceso.returncode == 0, salida
    assert int(resumen.group(2)) == 0, salida
