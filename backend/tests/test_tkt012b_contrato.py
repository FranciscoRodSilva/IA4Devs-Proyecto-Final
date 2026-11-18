"""Conformidad del borrador OpenAPI con el servidor, fila A8 de TKT-012b (TC-53; TC-54 lo cubre `npm run tipos:verificar`).

Las cinco operaciones del mantenimiento y del ciclo de vida de la obra (`actualizar_obra`, `eliminar_obra`,
`suspender_obra`, `reactivar_obra`, `cerrar_obra`) existen ya en el servidor (fila A7). Esta prueba compara el
borrador `docs/api/openapi.yaml` con lo que publica `/openapi.json` de la aplicación real y fija lo que el
borrador debe decir para ser el contrato de este ticket (diseño, «API»: lista de cambios del borrador). No
usa base de datos ni Docker: construye la aplicación sin motor, como `test_tkt017_api_congelado.py`, y lee
el borrador con el cargador compartido de `herramientas/soporte_tkt017_api.py`.

Qué compara y por qué así:

- **Método, ruta y `operationId`** del borrador frente a los publicados. El cliente TypeScript se genera de
  los `operationId`; un nombre distinto rompe la generación sin avisar.
- **Códigos de respuesta.** FastAPI publica solo `200`/`204` y `422` (los `401`, `403`, `404` y `409` los
  produce el contrato de error y no aparecen en `/openapi.json`), así que la conformidad se exige en tres
  direcciones: el código de éxito es el mismo, todo código que publica el servidor lo declara el borrador, y
  el borrador declara el conjunto exacto de la tabla «API» del diseño. `DELETE` responde `422` cuando
  `obra_id` no es un UUID (TC-52), de modo que el borrador debe declararlo.
- **`x-tickets`** de las cinco es exactamente `[TKT-012b]`.
- **`AccionBitacora`** tiene los 24 verbos con `ELIMINAR` al final y coincide, valor por valor, con el
  enumerado de `auditoria`. **`CodigoConflicto` no cambió**: sigue siendo el catálogo cerrado de 26 códigos.
- **`reactivar_obra`** ya no se declara `(asumido)`: D-2 lo confirmó (2026-11-17).
- **`ObraCambios`** cierra los campos desconocidos (`additionalProperties: false`) y publica solo los seis
  campos editables, ninguno obligatorio.
- **Los `409` documentados con un ejemplo que el esquema `ErrorConflictoEstado` acepta**, con el mensaje, el
  detalle y las acciones que el servidor produce de verdad (fijados en `test_tkt012b_api_obras.py`).

Rojo esperado de la fila: el borrador sigue como lo dejó TKT-012 (`x-tickets: [TKT-012]`, `(asumido)`,
`ObraCambios` abierto, el `409` de `eliminar_obra` con otro detalle y los demás `409` como `$ref` genérico a
`Conflicto`). Nacen en verde, a propósito, lo que A1 y A7 ya dejaron hecho: el enumerado `AccionBitacora`, el
catálogo `CodigoConflicto`, los seis campos de `ObraCambios`, y el método, la ruta, el `operationId` y el
código de éxito de las cinco operaciones.

TC-54 (los tipos generados del cliente difieren de los versionados si el borrador o el contrato cambian) no
tiene prueba de Python: lo hace `npm run tipos:verificar` desde `frontend/`.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

import pytest

from cimenta.auditoria.dominio.asiento import AccionBitacora
from contrato_error.catalogos import CodigoConflicto
from herramientas.soporte_tkt017_api import (
    borrador,
    resolver,
    validar_contra,
)
from herramientas.soporte_tkt017_api import publicado as contrato_publicado

TICKET = "TKT-012b"
RUTA_OBRA = "/obras/{obra_id}"

# (operationId, método, sufijo de la ruta, código de éxito) de las cinco operaciones de TKT-012b.
OPERACIONES = [
    pytest.param("actualizar_obra", "patch", "", "200", id="actualizar_obra"),
    pytest.param("eliminar_obra", "delete", "", "204", id="eliminar_obra"),
    pytest.param("suspender_obra", "post", "/suspension", "200", id="suspender_obra"),
    pytest.param("reactivar_obra", "post", "/reactivacion", "200", id="reactivar_obra"),
    pytest.param("cerrar_obra", "post", "/cierre", "200", id="cerrar_obra"),
]
TRANSICIONES = [
    pytest.param("suspender_obra", "SUSPENDER", id="suspender_obra"),
    pytest.param("reactivar_obra", "REACTIVAR", id="reactivar_obra"),
    pytest.param("cerrar_obra", "CERRAR", id="cerrar_obra"),
]
METODO_Y_SUFIJO = {
    "actualizar_obra": ("patch", ""),
    "eliminar_obra": ("delete", ""),
    "suspender_obra": ("post", "/suspension"),
    "reactivar_obra": ("post", "/reactivacion"),
    "cerrar_obra": ("post", "/cierre"),
}

# Los códigos que el borrador declara por operación (tabla «API» del diseño). `eliminar_obra` suma el `422`
# del `obra_id` mal formado, que el servidor publica (TC-52).
CODIGOS_DEL_BORRADOR = {
    "actualizar_obra": {"200", "401", "403", "404", "409", "422"},
    "eliminar_obra": {"204", "401", "403", "404", "409", "422"},
    "suspender_obra": {"200", "401", "403", "404", "409", "422"},
    "reactivar_obra": {"200", "401", "403", "404", "409", "422"},
    "cerrar_obra": {"200", "401", "403", "404", "409", "422"},
}

# D-2: lo que admite cada estado, en el orden de `OperacionObra`, y la acción (clave, sufijo de ruta) de cada una.
ADMITIDAS_POR_ESTADO = {
    "PLANEACION": ["CERRAR"],
    "ACTIVA": ["SUSPENDER", "CERRAR"],
    "SUSPENDIDA": ["REACTIVAR", "CERRAR"],
    "CERRADA": [],
}
ACCION_DE_OPERACION = {
    "SUSPENDER": ("SUSPENDER_OBRA", "suspension"),
    "REACTIVAR": ("REACTIVAR_OBRA", "reactivacion"),
    "CERRAR": ("CERRAR_OBRA", "cierre"),
}
# Las acciones del `409` `OBRA_CON_HISTORIAL`: solo las dos que ese rechazo ofrece (nunca `REACTIVAR_OBRA`).
ACCION_DE_HISTORIAL = {
    "SUSPENDER_OBRA": "suspension",
    "CERRAR_OBRA": "cierre",
}

MENSAJE_ESTADO = re.compile(
    r"^La obra (?P<codigo>\S+) está en (?P<estado>PLANEACION|ACTIVA|SUSPENDIDA|CERRADA)"
    r" y no admite esta operación\.$"
)
MENSAJE_CON_HISTORIAL = re.compile(r"^La obra \S+ tiene historial y no se puede eliminar\.$")
RUTA_DE_ACCION = re.compile(
    r"^/api/v1/obras/(?P<obra>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
    r"/(?P<sufijo>[a-z]+)$"
)

DETALLE_DE_HISTORIAL = {
    "linea_base_congelada": bool,
    "lineas_base": int,
    "importaciones": int,
    "movimientos": int,
}


# --------------------------------------------------------------------------- ayudas


@pytest.fixture(scope="module")
def contrato() -> Iterator[dict[str, Any]]:
    """El `/openapi.json` de la aplicación real, construido una sola vez (sin base ni Docker)."""
    with pytest.MonkeyPatch.context() as parche:
        yield contrato_publicado(parche)


def _operacion_del_borrador(identificador: str) -> dict[str, Any]:
    metodo, sufijo = METODO_Y_SUFIJO[identificador]
    operacion: dict[str, Any] = borrador()["paths"][f"{RUTA_OBRA}{sufijo}"][metodo]
    assert operacion["operationId"] == identificador
    return operacion


def _respuesta_409(identificador: str) -> dict[str, Any]:
    """La respuesta `409` del borrador con sus `$ref` resueltos (una en línea o un componente propio)."""
    respuesta = _operacion_del_borrador(identificador)["responses"]["409"]
    return dict(resolver(borrador(), respuesta))


def _ejemplos_de(respuesta: dict[str, Any]) -> list[dict[str, Any]]:
    """Los ejemplos del cuerpo JSON de una respuesta: `example` y cada `examples.*.value`."""
    contenido = respuesta.get("content", {}).get("application/json", {})
    ejemplos: list[dict[str, Any]] = []
    if "example" in contenido:
        ejemplos.append(contenido["example"])
    ejemplos.extend(ejemplo["value"] for ejemplo in contenido.get("examples", {}).values())
    return ejemplos


def _ejemplos_409(identificador: str) -> list[dict[str, Any]]:
    """Los ejemplos del `409` de una operación; vacío si el borrador la deja como `$ref` genérico."""
    respuesta = _respuesta_409(identificador)
    esquema = respuesta.get("content", {}).get("application/json", {}).get("schema")
    assert esquema == {"$ref": "#/components/schemas/ErrorConflictoEstado"}, (
        f"{identificador}: el 409 debe declarar el esquema ErrorConflictoEstado, no {esquema!r}"
    )
    ejemplos = _ejemplos_de(respuesta)
    assert ejemplos, f"{identificador}: el 409 no trae ningún ejemplo"
    for ejemplo in ejemplos:
        validar_contra("ErrorConflictoEstado", ejemplo)
    return ejemplos


def _acciones_de(ejemplo: dict[str, Any]) -> list[tuple[str, str, str, str]]:
    """Cada acción del ejemplo como (clave, método, id de obra, sufijo de la ruta); la ruta debe ser absoluta y de una obra."""
    acciones = []
    for accion in ejemplo["acciones"]:
        assert set(accion) == {"clave", "metodo", "ruta"}, accion
        coincidencia = RUTA_DE_ACCION.match(accion["ruta"])
        assert coincidencia is not None, f"Ruta de acción no absoluta o sin obra: {accion['ruta']}"
        acciones.append(
            (accion["clave"], accion["metodo"], coincidencia["obra"], coincidencia["sufijo"])
        )
    return acciones


def _texto(*nodos: object) -> str:
    return "\n".join(str(nodo) for nodo in nodos if nodo)


# --------------------------------------------------------------------------- TC-53 · las cinco operaciones


@pytest.mark.parametrize(("identificador", "metodo", "sufijo", "exito"), OPERACIONES)
def test_tkt012b_tc53_la_operacion_del_borrador_esta_publicada_con_su_metodo_ruta_y_operation_id(
    identificador: str, metodo: str, sufijo: str, exito: str, contrato: dict[str, Any]
) -> None:
    """TC-53 · DoD — método, ruta y `operationId` del borrador son los de `/openapi.json`.

    El borrador escribe la ruta sin el prefijo `/api/v1`; el servidor la publica con él.
    """
    del_borrador = borrador()["paths"][f"{RUTA_OBRA}{sufijo}"][metodo]
    ruta_publicada = f"/api/v1{RUTA_OBRA}{sufijo}"

    assert ruta_publicada in contrato["paths"], f"El servidor no publica {ruta_publicada}"
    publicada = contrato["paths"][ruta_publicada].get(metodo)
    assert publicada is not None, f"El servidor no publica {metodo.upper()} {ruta_publicada}"
    assert publicada["operationId"] == del_borrador["operationId"] == identificador


@pytest.mark.parametrize(("identificador", "metodo", "sufijo", "exito"), OPERACIONES)
def test_tkt012b_tc53_el_codigo_de_exito_publicado_es_el_del_borrador(
    identificador: str, metodo: str, sufijo: str, exito: str, contrato: dict[str, Any]
) -> None:
    """TC-53 · DoD — el código de éxito (`200`, y `204` sin cuerpo en `DELETE`) es el mismo en el borrador y en el servidor."""
    del_borrador = borrador()["paths"][f"{RUTA_OBRA}{sufijo}"][metodo]["responses"]
    publicada = contrato["paths"][f"/api/v1{RUTA_OBRA}{sufijo}"][metodo]["responses"]

    exitos_del_borrador = {codigo for codigo in del_borrador if codigo.startswith("2")}
    exitos_publicados = {codigo for codigo in publicada if codigo.startswith("2")}
    assert exitos_del_borrador == exitos_publicados == {exito}


@pytest.mark.parametrize(("identificador", "metodo", "sufijo", "exito"), OPERACIONES)
def test_tkt012b_tc53_el_borrador_declara_los_codigos_de_respuesta_que_publica_el_servidor(
    identificador: str, metodo: str, sufijo: str, exito: str, contrato: dict[str, Any]
) -> None:
    """TC-53 · DoD — el borrador declara el conjunto exacto de códigos de la tabla «API», y entre ellos todo lo que el servidor publica.

    `eliminar_obra` debe declarar también el `422` del `obra_id` que no es UUID: el servidor lo publica
    (TC-52) y el borrador de TKT-012 no lo tenía.
    """
    declarados = set(borrador()["paths"][f"{RUTA_OBRA}{sufijo}"][metodo]["responses"])
    publicados = set(contrato["paths"][f"/api/v1{RUTA_OBRA}{sufijo}"][metodo]["responses"])

    assert publicados <= declarados, (
        f"El servidor publica {sorted(publicados - declarados)} sin que el borrador lo declare"
    )
    assert declarados == CODIGOS_DEL_BORRADOR[identificador]


@pytest.mark.parametrize(("identificador", "metodo", "sufijo", "exito"), OPERACIONES)
def test_tkt012b_tc53_x_tickets_de_la_operacion_es_exactamente_tkt_012b(
    identificador: str, metodo: str, sufijo: str, exito: str
) -> None:
    """TC-53 · D-DIS-7 — `x-tickets` de las cinco operaciones pasa de `[TKT-012]` a `[TKT-012b]`.

    Es lo que reconocen los filtros de `test_tkt017_api_congelado.py` (TC-B19) para el conjunto de
    operaciones de `presupuesto`; el borrador no puede conservar `TKT-012` en estas cinco.
    """
    operacion = borrador()["paths"][f"{RUTA_OBRA}{sufijo}"][metodo]

    assert operacion["x-tickets"] == [TICKET]


# --------------------------------------------------------------------------- TC-53 · los esquemas


def test_tkt012b_tc53_accion_bitacora_del_borrador_tiene_24_verbos_con_eliminar_al_final() -> None:
    """TC-53 · CA-5 · HDU-001 esc. 20 — `AccionBitacora` del borrador es el enumerado de `auditoria`, verbo por verbo y en su orden.

    Nace en verde: la fila A1 añadió `ELIMINAR` al borrador junto con la migración `0017`. Esta prueba lo
    ata al enumerado de `auditoria` para que ninguno de los dos se mueva sin el otro.
    """
    verbos = borrador()["components"]["schemas"]["AccionBitacora"]["enum"]

    assert len(verbos) == 24
    assert verbos[-1] == "ELIMINAR"
    assert verbos[-2] == "DAR_BAJA"
    assert verbos == [accion.value for accion in AccionBitacora]


def test_tkt012b_tc53_codigo_conflicto_no_cambio_y_trae_los_dos_codigos_del_ticket() -> None:
    """TC-53 · D-DIS-7 — `CodigoConflicto` conserva sus 26 códigos, y `OBRA_CON_HISTORIAL` y `ESTADO_NO_PERMITE_OPERACION` ya estaban.

    El catálogo es cerrado: ampliarlo exigiría un caso nuevo, y TKT-012b no lo trae. Se compara con el
    catálogo del código (`contrato_error`) en su orden.
    """
    codigos = borrador()["components"]["schemas"]["CodigoConflicto"]["enum"]

    assert len(codigos) == 26
    assert {"OBRA_CON_HISTORIAL", "ESTADO_NO_PERMITE_OPERACION"} <= set(codigos)
    assert codigos == [codigo.value for codigo in CodigoConflicto]


def test_tkt012b_tc53_obra_cambios_del_borrador_cierra_los_campos_desconocidos() -> None:
    """TC-53 · CA-2 — `ObraCambios` declara `additionalProperties: false`: `codigo`, `tipo_contrato` y `estado` no se aceptan.

    El servidor ya lo publica así (A7); el borrador debe decir lo mismo para que el cliente generado y la
    documentación no sugieran que el `PATCH` acepta cualquier campo.
    """
    cambios = borrador()["components"]["schemas"]["ObraCambios"]

    assert cambios.get("additionalProperties") is False


def test_tkt012b_tc53_obra_cambios_del_borrador_publica_solo_los_seis_campos_opcionales(
    contrato: dict[str, Any],
) -> None:
    """TC-53 · CA-1 · CA-2 — `ObraCambios`: solo `nombre`, `domicilio`, los dos porcentajes, `iva_acreditable` y `umbral_alerta_pct`; ninguno obligatorio; al menos uno presente.

    Los mismos seis que publica el servidor. Nace en verde: el borrador de TKT-012 ya los traía.
    """
    cambios = borrador()["components"]["schemas"]["ObraCambios"]
    publicados = contrato["components"]["schemas"]["ObraCambios"]

    assert set(cambios["properties"]) == {
        "nombre",
        "domicilio",
        "retencion_destajo_pct",
        "fondo_garantia_pct",
        "iva_acreditable",
        "umbral_alerta_pct",
    }
    assert set(cambios["properties"]) == set(publicados["properties"])
    assert not cambios.get("required")
    assert cambios["minProperties"] == 1


def test_tkt012b_tc53_reactivar_obra_ya_no_se_declara_asumido() -> None:
    """TC-53 · D-2 — la descripción de `reactivar_obra` pierde el `(asumido)` y el «Pendiente de confirmar»: la persona dueña confirmó la vuelta de `SUSPENDIDA` a `ACTIVA` el 2026-11-17."""
    operacion = _operacion_del_borrador("reactivar_obra")
    descripcion = operacion.get("description", "")

    assert "(asumido)" not in descripcion
    assert "Pendiente de confirmar" not in descripcion


# --------------------------------------------------------------------------- TC-53 · actualizar_obra


def test_tkt012b_tc53_actualizar_obra_documenta_que_un_cuerpo_con_campos_fijos_es_422() -> None:
    """TC-53 · CA-2 — la descripción de `actualizar_obra` dice que `codigo`, `tipo_contrato` o `estado` en el cuerpo responden `422`."""
    descripcion = _operacion_del_borrador("actualizar_obra")["description"]

    assert "422" in descripcion
    for campo in ("codigo", "tipo_contrato", "estado"):
        assert campo in descripcion, campo


def test_tkt012b_tc53_actualizar_obra_documenta_que_umbral_alerta_pct_null_borra_el_umbral() -> (
    None
):
    """TC-53 · CA-1 variante — en la operación o en el campo de `ObraCambios` consta que `umbral_alerta_pct: null` borra el umbral."""
    operacion = _operacion_del_borrador("actualizar_obra")
    umbral = borrador()["components"]["schemas"]["ObraCambios"]["properties"]["umbral_alerta_pct"]

    texto = _texto(operacion.get("description"), umbral.get("description"))

    assert "null" in texto
    assert re.search(r"\bborra", texto, re.IGNORECASE), texto


def test_tkt012b_tc53_actualizar_obra_documenta_el_409_estado_no_permite_operacion() -> None:
    """TC-53 · CA-4 — el `409` de `actualizar_obra` es `ESTADO_NO_PERMITE_OPERACION` con la obra `CERRADA`, `detalle {estado}` y sin acciones.

    La edición solo se bloquea en `CERRADA` (D-3), y una obra cerrada no admite ninguna operación: por eso
    el ejemplo no ofrece acciones. El mensaje es el que produce el servidor.
    """
    ejemplos = _ejemplos_409("actualizar_obra")

    for ejemplo in ejemplos:
        assert ejemplo["tipo"] == "CONFLICTO"
        assert ejemplo["codigo"] == "ESTADO_NO_PERMITE_OPERACION"
        coincidencia = MENSAJE_ESTADO.match(ejemplo["mensaje"])
        assert coincidencia is not None, ejemplo["mensaje"]
        assert coincidencia["estado"] == "CERRADA"
        assert ejemplo["detalle"] == {"estado": "CERRADA"}
        assert ejemplo["acciones"] == []


# --------------------------------------------------------------------------- TC-53 · eliminar_obra


def test_tkt012b_tc53_eliminar_obra_documenta_el_409_obra_con_historial_con_su_detalle() -> None:
    """HDU-001 esc. 20 · TC-53 · CA-6 · RN-01 — el ejemplo del `409` es `OBRA_CON_HISTORIAL` con el mensaje del servidor y `detalle {linea_base_congelada, lineas_base, importaciones, movimientos}`.

    Un booleano y tres enteros no negativos. Una línea base congelada implica al menos una línea base.
    """
    ejemplos = _ejemplos_409("eliminar_obra")

    for ejemplo in ejemplos:
        assert ejemplo["tipo"] == "CONFLICTO"
        assert ejemplo["codigo"] == "OBRA_CON_HISTORIAL"
        assert MENSAJE_CON_HISTORIAL.match(ejemplo["mensaje"]), ejemplo["mensaje"]
        detalle = ejemplo["detalle"]
        assert set(detalle) == set(DETALLE_DE_HISTORIAL)
        for campo, tipo in DETALLE_DE_HISTORIAL.items():
            assert type(detalle[campo]) is tipo, campo
            if tipo is int:
                assert detalle[campo] >= 0, campo
        if detalle["linea_base_congelada"]:
            assert detalle["lineas_base"] >= 1


def test_tkt012b_tc53_eliminar_obra_ofrece_en_su_409_solo_acciones_de_obra_que_el_servidor_produce() -> (
    None
):
    """TC-53 · CA-6 · CA-9 — las acciones del ejemplo son `SUSPENDER_OBRA` y `CERRAR_OBRA`, `POST`, con la ruta absoluta de una misma obra y en ese orden.

    Nunca `REACTIVAR_OBRA`: una obra con historial se suspende o se cierra, y la reactivación no es salida de
    un borrado. Al menos un ejemplo ofrece alguna acción (desde `CERRADA` no habría ninguna).
    """
    ejemplos = _ejemplos_409("eliminar_obra")

    assert any(ejemplo["acciones"] for ejemplo in ejemplos)
    for ejemplo in ejemplos:
        acciones = _acciones_de(ejemplo)
        claves = [clave for clave, *_ in acciones]
        assert claves == [clave for clave in ACCION_DE_HISTORIAL if clave in claves], claves
        assert len(claves) == len(set(claves))
        assert len({obra for *_, obra, _ in acciones}) <= 1
        for clave, metodo, _, sufijo in acciones:
            assert clave in ACCION_DE_HISTORIAL, clave
            assert metodo == "POST"
            assert sufijo == ACCION_DE_HISTORIAL[clave]


def test_tkt012b_tc53_eliminar_obra_declara_que_sus_acciones_dependen_del_estado() -> None:
    """TC-53 · CA-6 — la operación o su `409` dicen que las acciones dependen del estado de la obra y nombran `SUSPENDER_OBRA` y `CERRAR_OBRA`.

    Solo cuentan las descripciones, no el ejemplo: el ejemplo muestra un caso y el texto explica la regla
    (desde `PLANEACION` y `SUSPENDIDA`, solo cerrar; desde `CERRADA`, ninguna).
    """
    operacion = _operacion_del_borrador("eliminar_obra")

    texto = _texto(operacion.get("description"), _respuesta_409("eliminar_obra").get("description"))

    assert "SUSPENDER_OBRA" in texto
    assert "CERRAR_OBRA" in texto
    assert re.search(r"\bestado\b", texto, re.IGNORECASE), texto


# --------------------------------------------------------------------------- TC-53 · las tres transiciones


@pytest.mark.parametrize(("identificador", "operacion"), TRANSICIONES)
def test_tkt012b_tc53_la_transicion_documenta_el_409_con_estado_y_operaciones_admitidas(
    identificador: str, operacion: str
) -> None:
    """HDU-001 esc. 20 · TC-53 · CA-9 — el `409` es `ESTADO_NO_PERMITE_OPERACION` con `detalle {estado, operaciones_admitidas}` y una acción `POST` por operación admitida.

    Cada ejemplo es coherente con la máquina de estados de D-2: `operaciones_admitidas` es lo que admite el
    `estado` del detalle, el mensaje cita ese mismo estado, y las acciones siguen ese orden con su clave y
    su ruta (`SUSPENDER_OBRA` a `/suspension`, `REACTIVAR_OBRA` a `/reactivacion`, `CERRAR_OBRA` a
    `/cierre`) sobre una misma obra. Al menos un ejemplo es un rechazo real de **esta** operación: el estado
    no la admite.
    """
    ejemplos = _ejemplos_409(identificador)

    for ejemplo in ejemplos:
        assert ejemplo["tipo"] == "CONFLICTO"
        assert ejemplo["codigo"] == "ESTADO_NO_PERMITE_OPERACION"
        coincidencia = MENSAJE_ESTADO.match(ejemplo["mensaje"])
        assert coincidencia is not None, ejemplo["mensaje"]
        estado = coincidencia["estado"]
        assert ejemplo["detalle"] == {
            "estado": estado,
            "operaciones_admitidas": ADMITIDAS_POR_ESTADO[estado],
        }
        acciones = _acciones_de(ejemplo)
        assert [(clave, metodo, sufijo) for clave, metodo, _, sufijo in acciones] == [
            (ACCION_DE_OPERACION[admitida][0], "POST", ACCION_DE_OPERACION[admitida][1])
            for admitida in ADMITIDAS_POR_ESTADO[estado]
        ]
        assert len({obra for _, _, obra, _ in acciones}) <= 1
    assert any(
        operacion not in ejemplo["detalle"]["operaciones_admitidas"] for ejemplo in ejemplos
    ), f"Ningún ejemplo es un rechazo de {operacion}"
