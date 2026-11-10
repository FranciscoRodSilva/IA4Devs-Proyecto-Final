"""Entorno de prueba de TKT-017 sobre la base real: lo comparten la confirmación (a3) y el congelado (b1).

`Base` lee la base de la prueba con una conexión propia del rol de aplicación; `Entorno` arma la obra
`AP-058-25` en planeación, los tipos de partida sembrados y un director que confirma importaciones por
la interfaz publicada `cimenta.presupuesto.interfaz.materializar_importacion`. `Hilo` corre una función
en un hilo y guarda su resultado o su excepción, para las pruebas de concurrencia.

Son ayudantes de prueba: ningún código de producción los importa.
"""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable, Mapping
from decimal import Decimal
from typing import TYPE_CHECKING, Any, LiteralString

import psycopg
import pytest

from cimenta.presupuesto.aplicacion.congelado import congelar_linea_base
from cimenta.presupuesto.aplicacion.contexto import ContextoPresupuesto
from cimenta.presupuesto.dominio.preparacion_importacion import Preparacion
from cimenta.presupuesto.infraestructura.preparacion_json import preparacion_a_json
from cimenta.presupuesto.interfaz import LineaBaseMaterializada, materializar_importacion
from contrato_error.excepciones import ErrorContrato
from herramientas.soporte_tkt017 import foto_de_base, preparacion_sintetica

if TYPE_CHECKING:
    # `conftest` no es importable en tiempo de ejecución: pytest lo carga por su cuenta.
    from conftest import DatosPresupuesto

Contexto = Callable[[], ContextoPresupuesto]

CODIGO_OBRA = "AP-058-25"
NOMBRE_COMPLETO_OBRA = "AP-058-25 · Obra AP-058-25"
LIMITE_DE_HILO = 10.0
MOTIVO_DE_CONGELADO = "Firma de contrato 2026-11-04"


def materializar(
    contexto: ContextoPresupuesto,
    importacion_id: uuid.UUID,
    *,
    asignacion: Mapping[str, uuid.UUID],
    usuario_id: uuid.UUID,
    reemplazar_borrador: bool = False,
    motivo_reemplazo: str | None = None,
) -> LineaBaseMaterializada:
    """La firma exacta de «Aplicación» en el diseño, por la interfaz publicada."""
    return materializar_importacion(
        contexto,
        importacion_id=importacion_id,
        asignacion_tipos_partida=asignacion,
        reemplazar_borrador=reemplazar_borrador,
        motivo_reemplazo=motivo_reemplazo,
        usuario_id=usuario_id,
    )


def congelar(
    contexto: ContextoPresupuesto,
    linea_base_id: uuid.UUID,
    *,
    usuario_id: uuid.UUID,
    motivo: str = MOTIVO_DE_CONGELADO,
) -> uuid.UUID:
    """La firma exacta de «Aplicación» en el diseño de TKT-017b, `congelar_linea_base`."""
    return congelar_linea_base(
        contexto, linea_base_id=linea_base_id, motivo=motivo, usuario_id=usuario_id
    )


_VOLCADO: dict[str, LiteralString] = {
    "linea_base": "SELECT * FROM linea_base WHERE obra_id = %s ORDER BY id",
    "nivel": "SELECT * FROM nivel WHERE obra_id = %s ORDER BY id",
    "area": "SELECT a.* FROM area a JOIN nivel n ON n.id = a.nivel_id "
    "WHERE n.obra_id = %s ORDER BY a.id",
    "partida": "SELECT p.* FROM partida p JOIN area a ON a.id = p.area_id "
    "JOIN nivel n ON n.id = a.nivel_id WHERE n.obra_id = %s ORDER BY p.id",
    "concepto": "SELECT * FROM concepto WHERE obra_id = %s ORDER BY id",
    "partida_concepto": "SELECT pc.* FROM partida_concepto pc "
    "JOIN concepto c ON c.id = pc.concepto_id WHERE c.obra_id = %s ORDER BY pc.id",
    "apu": "SELECT a.* FROM apu a JOIN concepto c ON c.id = a.concepto_id "
    "WHERE c.obra_id = %s ORDER BY a.id",
    "apu_insumo": "SELECT ai.* FROM apu_insumo ai JOIN apu a ON a.id = ai.apu_id "
    "JOIN concepto c ON c.id = a.concepto_id WHERE c.obra_id = %s ORDER BY ai.id",
    "apu_cargo": "SELECT ac.* FROM apu_cargo ac JOIN apu a ON a.id = ac.apu_id "
    "JOIN concepto c ON c.id = a.concepto_id WHERE c.obra_id = %s ORDER BY ac.id",
}


class Base:
    """Lectura de la base de la prueba con una conexión propia del rol de aplicación."""

    def __init__(self, conexion: psycopg.Connection[tuple[Any, ...]]) -> None:
        self.conexion = conexion

    def filas(self, consulta: LiteralString, *parametros: object) -> list[tuple[Any, ...]]:
        """Las filas, con los `Decimal` como cadena para comprobar también la escala de la columna."""
        crudas = self.conexion.execute(consulta, parametros).fetchall()
        return [tuple(str(c) if isinstance(c, Decimal) else c for c in fila) for fila in crudas]

    def ejecutar(self, consulta: LiteralString, *parametros: object) -> None:
        self.conexion.execute(consulta, parametros)

    def foto(self) -> dict[str, object]:
        return foto_de_base(self.conexion)

    def volcado_de_obra(self, obra_id: uuid.UUID) -> dict[str, list[tuple[Any, ...]]]:
        """Todas las columnas de las filas de la obra en las ocho tablas de su jerarquía y su línea base."""
        return {tabla: self.filas(consulta, obra_id) for tabla, consulta in _VOLCADO.items()}


class Entorno:
    """Obra `AP-058-25` en planeación, los tipos de partida sembrados y un director que confirma."""

    def __init__(self, datos: DatosPresupuesto, base: Base) -> None:
        self.datos = datos
        self.base = base
        self.usuario_id = datos.usuario()
        self.obra_id = datos.obra(codigo=CODIGO_OBRA, creado_por_id=self.usuario_id)
        self.tipo_muros = datos.tipo_partida(clave="MUROS")
        self.tipo_plafon = datos.tipo_partida(clave="PLAFONES_Y_CAJILLOS")
        self.importacion_id: uuid.UUID = uuid.uuid4()

    def asignacion(self) -> dict[str, uuid.UUID]:
        """La de `CA-A1`: `MUROS EXTERIORES` → MUROS y `PLAFON` → PLAFONES_Y_CAJILLOS."""
        return {"MUROS EXTERIORES": self.tipo_muros, "PLAFON": self.tipo_plafon}

    def registrar_mano_obra(
        self,
        *,
        codigo: str = "MO-001",
        descripcion: str = "OFICIAL TABLAROQUERO",
        unidad: str = "JORNAL",
        tipo: str = "MANO_OBRA",
    ) -> uuid.UUID:
        """El insumo de mano de obra que el análisis de `preparacion_sintetica()` resuelve por descripción."""
        return self.datos.insumo(codigo=codigo, descripcion=descripcion, tipo=tipo, unidad=unidad)

    def importar(
        self,
        *,
        estado: str = "VALIDADO",
        preparacion: Preparacion | None = None,
        documento: Mapping[str, object] | None = None,
        obra_id: uuid.UUID | None = None,
    ) -> uuid.UUID:
        """Una importación de la obra con la preparación pedida (por omisión, la sintética de `CA-A1`).

        `RECIBIDO` y `ANALIZANDO` no admiten preparación (`ck_importacion_preparacion_tras_analisis`).
        """
        if documento is None and estado not in ("RECIBIDO", "ANALIZANDO"):
            documento = preparacion_a_json(
                preparacion if preparacion is not None else preparacion_sintetica()
            )
        return self.datos.importacion(
            obra_id=obra_id if obra_id is not None else self.obra_id,
            estado=estado,
            preparacion=documento,
            importado_por_id=self.usuario_id,
        )

    def poner_obra_en(self, estado: str) -> None:
        self.base.ejecutar("UPDATE obra SET estado = %s WHERE id = %s", estado, self.obra_id)

    def sembrar_congelada(self, *, obra_id: uuid.UUID | None = None) -> uuid.UUID:
        """Una línea base `CONGELADA` versión 1, en una obra que por eso ya está `ACTIVA`."""
        obra = obra_id if obra_id is not None else self.obra_id
        self.base.ejecutar("UPDATE obra SET estado = 'ACTIVA' WHERE id = %s", obra)
        return self.datos.linea_base(estado="CONGELADA", obra_id=obra, version=1)

    def sembrar_borrador_con_jerarquia(
        self, *, obra_id: uuid.UUID | None = None, version: int = 1
    ) -> uuid.UUID:
        """Un borrador con una jerarquía anterior (nivel, área, partida, concepto y aparición).

        Sembrado a mano: no tiene asiento `CONFIRMAR` en la bitácora ni análisis (`P-5`).
        """
        obra = obra_id if obra_id is not None else self.obra_id
        datos = self.datos
        partida = datos.partida(area_id=datos.area(nivel_id=datos.nivel(obra_id=obra)))
        datos.partida_concepto(
            concepto_id=datos.concepto(obra_id=obra, codigo="OLD-1"), partida_id=partida
        )
        return datos.linea_base(estado="BORRADOR", obra_id=obra, version=version)

    def confirmar(
        self,
        contexto: Contexto,
        *,
        importacion_id: uuid.UUID | None = None,
        asignacion: Mapping[str, uuid.UUID] | None = None,
        reemplazar_borrador: bool = False,
        motivo_reemplazo: str | None = None,
    ) -> LineaBaseMaterializada:
        return materializar(
            contexto(),
            importacion_id if importacion_id is not None else self.importacion_id,
            asignacion=asignacion if asignacion is not None else self.asignacion(),
            usuario_id=self.usuario_id,
            reemplazar_borrador=reemplazar_borrador,
            motivo_reemplazo=motivo_reemplazo,
        )

    def rechazo(
        self,
        contexto: Contexto,
        *,
        importacion_id: uuid.UUID | None = None,
        asignacion: Mapping[str, uuid.UUID] | None = None,
        reemplazar_borrador: bool = False,
        motivo_reemplazo: str | None = None,
    ) -> ErrorContrato:
        """Confirma, espera un `ErrorContrato` y comprueba que no cambió ninguna fila ni ningún estado."""
        antes = self.base.foto()
        with pytest.raises(ErrorContrato) as rechazo:
            self.confirmar(
                contexto,
                importacion_id=importacion_id,
                asignacion=asignacion,
                reemplazar_borrador=reemplazar_borrador,
                motivo_reemplazo=motivo_reemplazo,
            )
        assert self.base.foto() == antes, "Un rechazo no escribe: ninguna fila ni estado cambió"
        return rechazo.value


class Hilo[T](threading.Thread):
    """Un hilo que guarda el resultado o la excepción de su función, sin dejarla escapar."""

    def __init__(self, nombre: str, funcion: Callable[[], T]) -> None:
        super().__init__(name=nombre, daemon=True)
        self._funcion = funcion
        self.resultado: T | None = None
        self.error: BaseException | None = None

    def run(self) -> None:
        try:
            self.resultado = self._funcion()
        except BaseException as error:
            self.error = error

    def exito(self) -> T:
        assert self.resultado is not None, f"El hilo {self.name} no terminó bien: {self.error!r}"
        return self.resultado

    def terminar(self) -> None:
        self.join(timeout=LIMITE_DE_HILO)
        assert not self.is_alive(), f"El hilo {self.name} no terminó en {LIMITE_DE_HILO} s"
