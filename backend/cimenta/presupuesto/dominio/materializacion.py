"""Planificación de materialización de línea base desde preparación (TKT-017a2, fila A4).

Sin efectos secundarios salvo las llamadas a `nuevo_id`. Cuantiza antes de calcular (P-4 del
diseño): la preparación se valida y se cuantiza una sola vez, y el resto del módulo consume
valores que ya cumplen las columnas `NOT NULL` y la escala de su columna.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID

from cimenta.presupuesto.dominio.analisis import (
    AnalisisLeido,
    CargoLeido,
    InsumoLeido,
    InsumoPorCrear,
    TipoCargo,
    TipoInsumo,
)
from cimenta.presupuesto.dominio.catalogo import ConceptoLeido
from cimenta.presupuesto.dominio.explosion import (
    CausaRechazoExplosion,
    ExplosionCalculada,
    RechazoExplosion,
)
from cimenta.presupuesto.dominio.explosion_materializada import (
    CargoDeApu,
    FilaExplotable,
    InsumoDeApu,
    explotar_filas,
)
from cimenta.presupuesto.dominio.lectura_analisis import normalizar_clave_insumo
from cimenta.presupuesto.dominio.preparacion_importacion import Preparacion
from tipos_base import Cantidad, Dinero, Porcentaje, Rendimiento, sumar

_MSJ_PREPARACION = "la importación debe analizarse de nuevo"


@dataclass(frozen=True, slots=True)
class InsumoRegistrado:
    id: UUID
    codigo: str
    descripcion: str
    unidad: str
    tipo: TipoInsumo


@dataclass(frozen=True, slots=True)
class NivelNuevo:
    id: UUID
    nombre: str
    orden: int


@dataclass(frozen=True, slots=True)
class AreaNueva:
    id: UUID
    nivel_id: UUID
    nombre: str


@dataclass(frozen=True, slots=True)
class PartidaNueva:
    id: UUID
    area_id: UUID
    tipo_partida_id: UUID
    orden: int


@dataclass(frozen=True, slots=True)
class ConceptoNuevo:
    id: UUID
    codigo: str
    descripcion: str
    unidad: str


@dataclass(frozen=True, slots=True)
class PartidaConceptoNueva:
    id: UUID
    concepto_id: UUID
    partida_id: UUID
    cantidad: Cantidad
    precio_unitario: Dinero
    importe: Dinero


@dataclass(frozen=True, slots=True)
class InsumoNuevo:
    id: UUID
    codigo: str
    descripcion: str
    unidad: str
    tipo: TipoInsumo
    creado_en_importacion: bool


@dataclass(frozen=True, slots=True)
class ApuInsumoNuevo:
    insumo_id: UUID
    costo_unitario: Dinero
    rendimiento: Rendimiento
    cargo: Dinero


@dataclass(frozen=True, slots=True)
class ApuCargoNuevo:
    tipo: TipoCargo
    porcentaje: Porcentaje | None
    base_calculo: Dinero | None
    importe: Dinero


@dataclass(frozen=True, slots=True)
class ApuNuevo:
    id: UUID
    concepto_id: UUID
    hoja: str
    costo_material: Dinero
    costo_mano_obra: Dinero
    costo_directo: Dinero
    total_cargos: Dinero
    total_indirectos: Dinero
    precio_unitario: Dinero
    fecha_analisis: str | None
    analista: str | None
    insumos: tuple[ApuInsumoNuevo, ...]
    cargos: tuple[ApuCargoNuevo, ...]


@dataclass(frozen=True, slots=True)
class PlanMaterializacion:
    niveles: tuple[NivelNuevo, ...]
    areas: tuple[AreaNueva, ...]
    partidas: tuple[PartidaNueva, ...]
    conceptos: tuple[ConceptoNuevo, ...]
    partidas_concepto: tuple[PartidaConceptoNueva, ...]
    insumos_insertar: tuple[InsumoNuevo, ...]
    apus: tuple[ApuNuevo, ...]
    importe_venta: Dinero
    explosion: ExplosionCalculada


@dataclass(frozen=True, slots=True)
class AsignacionInvalida:
    """Rechazo de la asignación de tipos de partida (`422`).

    Los tres campos son nombres de partida normalizados con `strip().upper()`, ordenados y sin
    repetir. `faltantes`: partidas del catálogo sin tipo asignado. `inexistentes`: partidas cuyo
    tipo asignado no está en `tipos_partida`. `ambiguas`: nombres que dos claves de la asignación
    normalizan igual y apuntan a tipos distintos; solo se reportan las que corresponden a una
    partida del catálogo.
    """

    faltantes: tuple[str, ...]
    inexistentes: tuple[str, ...]
    ambiguas: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PreparacionInconsistente:
    motivo: str
    codigo_concepto: str | None


@dataclass(frozen=True, slots=True)
class InsumoEnConflicto:
    codigo: str
    unidad_importacion: str
    tipo_importacion: TipoInsumo
    unidad_registrada: str
    tipo_registrado: TipoInsumo


@dataclass(frozen=True, slots=True)
class ExplosionRechazada:
    causas: tuple[CausaRechazoExplosion, ...]


type ResultadoMaterializacion = (
    PlanMaterializacion
    | AsignacionInvalida
    | PreparacionInconsistente
    | InsumoEnConflicto
    | ExplosionRechazada
)


@dataclass(frozen=True, slots=True)
class _Ubicacion:
    """Nodos del catálogo que alcanza un concepto, con las filas que los identifican."""

    fila_nivel: int
    nombre_nivel: str
    fila_area: int
    nombre_area: str
    fila_partida: int
    nombre_partida: str

    @property
    def clave_area(self) -> tuple[int, int]:
        return (self.fila_nivel, self.fila_area)

    @property
    def clave_partida(self) -> tuple[int, int, int]:
        return (self.fila_nivel, self.fila_area, self.fila_partida)

    @property
    def nombre_asignable(self) -> str:
        return _normalizar_nombre(self.nombre_partida)


@dataclass(frozen=True, slots=True)
class _InsumoValidado:
    clave: str
    descripcion: str
    tipo: TipoInsumo
    unidad: str
    costo_unitario: Dinero
    rendimiento: Rendimiento
    cargo: Dinero


@dataclass(frozen=True, slots=True)
class _ConceptoValidado:
    """Una fila del catálogo con su análisis, sin nulos donde la columna es `NOT NULL` y cuantizada."""

    codigo: str
    descripcion: str
    unidad: str
    ubicacion: _Ubicacion
    cantidad: Cantidad
    precio_unitario: Dinero
    importe: Dinero
    hoja: str
    fecha_analisis: str | None
    analista: str | None
    costo_material: Dinero
    costo_mano_obra: Dinero
    costo_directo: Dinero
    total_cargos: Dinero
    total_indirectos: Dinero
    insumos: tuple[_InsumoValidado, ...]
    cargos: tuple[ApuCargoNuevo, ...]


@dataclass(frozen=True, slots=True)
class _Jerarquia:
    niveles: tuple[NivelNuevo, ...]
    areas: tuple[AreaNueva, ...]
    partidas: tuple[PartidaNueva, ...]
    partida_id_por_clave: Mapping[tuple[int, int, int], UUID]


class _ColumnaInvalida(Exception):
    """Un valor de la preparación falta o no cabe en la columna `NOT NULL` que lo recibe."""

    def __init__(self, columna: str) -> None:
        super().__init__(columna)
        self.columna = columna


def planificar_materializacion(
    preparacion: Preparacion,
    *,
    asignacion: Mapping[str, UUID],
    tipos_partida: frozenset[UUID],
    insumos_registrados: Sequence[InsumoRegistrado],
    nuevo_id: Callable[[], UUID],
) -> ResultadoMaterializacion:
    """Implementa CA-A1, CA-A3, CA-A5 y CA-A6 de TKT-017 (RN-01, PA-T8, PA-T13, PA-T17).

    Orden de rechazos: estructura, asignación, insumos, explosión, plan de filas (P-4).
    Sin efectos secundarios salvo las llamadas a nuevo_id.
    """
    validados = _validar_conceptos(preparacion)
    if isinstance(validados, PreparacionInconsistente):
        return validados

    tipo_por_nombre, ambiguas = _normalizar_asignacion(asignacion)
    rechazo_asignacion = _validar_asignacion(validados, tipo_por_nombre, ambiguas, tipos_partida)
    if rechazo_asignacion is not None:
        return rechazo_asignacion

    resolutor = _ResolutorDeInsumos(preparacion.insumos_por_crear, insumos_registrados, nuevo_id)
    resueltos_por_hoja = _resolver_insumos(validados, resolutor)
    if isinstance(resueltos_por_hoja, InsumoEnConflicto | PreparacionInconsistente):
        return resueltos_por_hoja

    filas = tuple(
        _fila_explotable(
            concepto,
            resueltos_por_hoja[concepto.hoja],
            tipo_por_nombre[concepto.ubicacion.nombre_asignable],
        )
        for concepto in validados
    )
    try:
        explosion = explotar_filas(filas)
    except ValueError:
        return PreparacionInconsistente(motivo="explosion_presupuesto", codigo_concepto=None)
    if isinstance(explosion, RechazoExplosion):
        return ExplosionRechazada(causas=explosion.causas)

    return _armar_plan(
        validados,
        tipo_por_nombre,
        resueltos_por_hoja,
        tuple(resolutor.insumos_nuevos),
        explosion,
        nuevo_id,
    )


def _normalizar_nombre(nombre: str) -> str:
    return nombre.strip().upper()


def _cuantizada[N: (Cantidad, Dinero, Rendimiento, Porcentaje)](valor: N | None, columna: str) -> N:
    """Cuantiza a la escala de la columna; nulo o fuera de rango se rechaza con su nombre."""
    if valor is None:
        raise _ColumnaInvalida(columna)
    try:
        return valor.cuantizar()
    except ValueError as error:
        raise _ColumnaInvalida(columna) from error


def _cuantizada_opcional[N: (Porcentaje, Dinero)](valor: N | None, columna: str) -> N | None:
    return None if valor is None else _cuantizada(valor, columna)


def _requerido[T](valor: T | None, columna: str) -> T:
    if valor is None:
        raise _ColumnaInvalida(columna)
    return valor


def _validar_conceptos(
    preparacion: Preparacion,
) -> tuple[_ConceptoValidado, ...] | PreparacionInconsistente:
    """Estructura y valores de cada concepto en orden de fila (CA-A5, invariante 39).

    Un código solo puede aparecer una vez en cada nodo de partida: la clave de duplicado es la
    ruta por filas más el código, no el nombre de la partida.
    """
    if not preparacion.conceptos:
        return PreparacionInconsistente(motivo=_MSJ_PREPARACION, codigo_concepto=None)

    validados: list[_ConceptoValidado] = []
    vistos: set[tuple[int, int, int, str]] = set()
    for concepto in sorted(preparacion.conceptos, key=lambda c: c.fila):
        inconsistente = PreparacionInconsistente(
            motivo=_MSJ_PREPARACION, codigo_concepto=concepto.codigo
        )
        ubicacion = _ubicacion_de(concepto)
        if ubicacion is None or concepto.descripcion is None or concepto.unidad is None:
            return inconsistente
        clave_duplicado = (*ubicacion.clave_partida, concepto.codigo)
        if clave_duplicado in vistos:
            return inconsistente
        vistos.add(clave_duplicado)
        analisis = _analisis_de_concepto(preparacion, concepto)
        if analisis is None:
            return inconsistente
        try:
            validado = _validar_valores(
                concepto, concepto.descripcion, concepto.unidad, ubicacion, analisis
            )
        except _ColumnaInvalida as error:
            return PreparacionInconsistente(motivo=error.columna, codigo_concepto=concepto.codigo)
        validados.append(validado)
    try:
        _cuantizada(sumar((c.importe for c in validados), Dinero), "linea_base.importe_venta")
    except _ColumnaInvalida as error:
        return PreparacionInconsistente(motivo=error.columna, codigo_concepto=None)
    return tuple(validados)


def _ubicacion_de(concepto: ConceptoLeido) -> _Ubicacion | None:
    nivel, area, partida = concepto.ruta.nivel, concepto.ruta.area, concepto.ruta.partida
    if nivel is None or area is None or partida is None:
        return None
    if nivel.nombre is None or area.nombre is None or partida.nombre is None:
        return None
    return _Ubicacion(
        fila_nivel=nivel.fila,
        nombre_nivel=nivel.nombre,
        fila_area=area.fila,
        nombre_area=area.nombre,
        fila_partida=partida.fila,
        nombre_partida=partida.nombre,
    )


def _analisis_de_concepto(
    preparacion: Preparacion, concepto: ConceptoLeido
) -> AnalisisLeido | None:
    asociaciones = [
        a
        for a in preparacion.asociaciones
        if a.codigo == concepto.codigo and concepto.fila in a.filas_catalogo
    ]
    if len(asociaciones) != 1:
        return None
    candidatos = [a for a in preparacion.analisis if a.hoja == asociaciones[0].hoja]
    if len(candidatos) != 1:
        return None
    return candidatos[0]


def _validar_valores(
    concepto: ConceptoLeido,
    descripcion: str,
    unidad: str,
    ubicacion: _Ubicacion,
    analisis: AnalisisLeido,
) -> _ConceptoValidado:
    """Comprueba los nulos y la escala de cada columna que recibirá el concepto.

    Lanza `_ColumnaInvalida` con el nombre de la primera columna que no se puede escribir.
    """
    cantidad = _cuantizada(concepto.cantidad, "partida_concepto.cantidad")
    totales = analisis.totales
    costo_material = _cuantizada(totales.material, "apu.costo_material")
    costo_mano_obra = _cuantizada(totales.mano_obra, "apu.costo_mano_obra")
    costo_directo = _cuantizada(totales.costo_directo, "apu.costo_directo")
    total_cargos = _cuantizada(totales.cargos, "apu.total_cargos")
    precio_unitario = _cuantizada(analisis.precio_unitario, "apu.precio_unitario")
    insumos = tuple(_validar_insumo(insumo) for insumo in analisis.insumos)
    cargos = tuple(_validar_cargo(cargo) for cargo in analisis.cargos)
    return _ConceptoValidado(
        codigo=concepto.codigo,
        descripcion=descripcion,
        unidad=unidad,
        ubicacion=ubicacion,
        cantidad=cantidad,
        precio_unitario=precio_unitario,
        importe=_cuantizada(cantidad * precio_unitario, "partida_concepto.importe"),
        hoja=analisis.hoja,
        fecha_analisis=analisis.cabecera.fecha,
        analista=analisis.cabecera.analista,
        costo_material=costo_material,
        costo_mano_obra=costo_mano_obra,
        costo_directo=costo_directo,
        total_cargos=total_cargos,
        total_indirectos=sumar(
            (cargo.importe for cargo in cargos if cargo.tipo == TipoCargo.INDIRECTOS), Dinero
        ),
        insumos=insumos,
        cargos=cargos,
    )


def _validar_insumo(insumo: InsumoLeido) -> _InsumoValidado:
    return _InsumoValidado(
        clave=insumo.clave,
        descripcion=insumo.descripcion,
        tipo=insumo.tipo,
        unidad=_requerido(insumo.unidad, "insumo.unidad"),
        costo_unitario=_cuantizada(insumo.costo_unitario, "apu_insumo.costo_unitario"),
        rendimiento=_cuantizada(insumo.rendimiento, "apu_insumo.rendimiento"),
        cargo=_cuantizada(insumo.cargo, "apu_insumo.cargo"),
    )


def _validar_cargo(cargo: CargoLeido) -> ApuCargoNuevo:
    return ApuCargoNuevo(
        tipo=_requerido(cargo.tipo, "apu_cargo.tipo"),
        porcentaje=_cuantizada_opcional(cargo.porcentaje, "apu_cargo.porcentaje"),
        base_calculo=_cuantizada_opcional(cargo.base, "apu_cargo.base_calculo"),
        importe=_cuantizada(cargo.importe, "apu_cargo.importe"),
    )


def _normalizar_asignacion(
    asignacion: Mapping[str, UUID],
) -> tuple[dict[str, UUID], frozenset[str]]:
    """Normaliza las claves una sola vez; las que colisionan con otro tipo quedan como ambiguas."""
    tipo_por_nombre: dict[str, UUID] = {}
    ambiguas: set[str] = set()
    for clave, tipo_partida_id in asignacion.items():
        nombre = _normalizar_nombre(clave)
        if tipo_por_nombre.setdefault(nombre, tipo_partida_id) != tipo_partida_id:
            ambiguas.add(nombre)
    return tipo_por_nombre, frozenset(ambiguas)


def _validar_asignacion(
    validados: Sequence[_ConceptoValidado],
    tipo_por_nombre: Mapping[str, UUID],
    ambiguas: frozenset[str],
    tipos_partida: frozenset[UUID],
) -> AsignacionInvalida | None:
    """Las claves sobrantes de la asignación, ambiguas o no, se ignoran (P-12)."""
    requeridas = sorted({c.ubicacion.nombre_asignable for c in validados})
    ambiguas_requeridas = tuple(nombre for nombre in requeridas if nombre in ambiguas)
    faltantes = tuple(nombre for nombre in requeridas if nombre not in tipo_por_nombre)
    inexistentes = tuple(
        nombre
        for nombre in requeridas
        if nombre in tipo_por_nombre
        and nombre not in ambiguas
        and tipo_por_nombre[nombre] not in tipos_partida
    )
    if faltantes or inexistentes or ambiguas_requeridas:
        return AsignacionInvalida(
            faltantes=faltantes, inexistentes=inexistentes, ambiguas=ambiguas_requeridas
        )
    return None


class _ResolutorDeInsumos:
    """Resuelve cada insumo del análisis contra las altas de la importación y lo ya registrado."""

    def __init__(
        self,
        altas: Sequence[InsumoPorCrear],
        registrados: Sequence[InsumoRegistrado],
        nuevo_id: Callable[[], UUID],
    ) -> None:
        self._altas = {alta.clave: alta for alta in altas}
        self._registrados = tuple(registrados)
        self._por_descripcion: dict[str, InsumoRegistrado] = {}
        for registrado in self._registrados:
            self._por_descripcion.setdefault(
                normalizar_clave_insumo(registrado.descripcion), registrado
            )
        self._nuevo_id = nuevo_id
        self._dados_de_alta: dict[str, InsumoRegistrado] = {}
        self.insumos_nuevos: list[InsumoNuevo] = []

    def resolver(
        self, insumo: _InsumoValidado, codigo_concepto: str
    ) -> InsumoRegistrado | InsumoEnConflicto | PreparacionInconsistente:
        alta = self._altas.get(insumo.clave)
        if alta is not None:
            return self._desde_alta(insumo, alta)
        registrado = self._por_descripcion.get(normalizar_clave_insumo(insumo.descripcion))
        if registrado is None:
            return PreparacionInconsistente(
                motivo=_MSJ_PREPARACION, codigo_concepto=codigo_concepto
            )
        return _sin_conflicto(insumo, registrado)

    def _desde_alta(
        self, insumo: _InsumoValidado, alta: InsumoPorCrear
    ) -> InsumoRegistrado | InsumoEnConflicto:
        registrado = next((r for r in self._registrados if r.codigo == insumo.clave), None)
        if registrado is not None:
            return _sin_conflicto(insumo, registrado)
        if insumo.clave not in self._dados_de_alta:
            nuevo = InsumoNuevo(
                id=self._nuevo_id(),
                codigo=insumo.clave,
                descripcion=alta.descripcion,
                unidad=alta.unidad,
                tipo=alta.tipo,
                creado_en_importacion=True,
            )
            self.insumos_nuevos.append(nuevo)
            self._dados_de_alta[insumo.clave] = InsumoRegistrado(
                id=nuevo.id,
                codigo=nuevo.codigo,
                descripcion=nuevo.descripcion,
                unidad=nuevo.unidad,
                tipo=nuevo.tipo,
            )
        return self._dados_de_alta[insumo.clave]


def _sin_conflicto(
    insumo: _InsumoValidado, registrado: InsumoRegistrado
) -> InsumoRegistrado | InsumoEnConflicto:
    if registrado.unidad != insumo.unidad or registrado.tipo != insumo.tipo:
        return InsumoEnConflicto(
            codigo=registrado.codigo,
            unidad_importacion=insumo.unidad,
            tipo_importacion=insumo.tipo,
            unidad_registrada=registrado.unidad,
            tipo_registrado=registrado.tipo,
        )
    return registrado


def _resolver_insumos(
    validados: Sequence[_ConceptoValidado],
    resolutor: _ResolutorDeInsumos,
) -> dict[str, tuple[InsumoRegistrado, ...]] | InsumoEnConflicto | PreparacionInconsistente:
    """Un insumo resuelto por cada insumo del análisis, por hoja; el primer rechazo corta."""
    resueltos_por_hoja: dict[str, tuple[InsumoRegistrado, ...]] = {}
    for concepto in validados:
        if concepto.hoja in resueltos_por_hoja:
            continue
        resueltos: list[InsumoRegistrado] = []
        for insumo in concepto.insumos:
            resultado = resolutor.resolver(insumo, concepto.codigo)
            if isinstance(resultado, InsumoEnConflicto | PreparacionInconsistente):
                return resultado
            resueltos.append(resultado)
        resueltos_por_hoja[concepto.hoja] = tuple(resueltos)
    return resueltos_por_hoja


def _fila_explotable(
    concepto: _ConceptoValidado,
    resueltos: Sequence[InsumoRegistrado],
    tipo_partida_id: UUID,
) -> FilaExplotable:
    return FilaExplotable(
        codigo_concepto=concepto.codigo,
        tipo_partida_id=tipo_partida_id,
        cantidad=concepto.cantidad,
        precio_unitario=concepto.precio_unitario,
        insumos=tuple(
            InsumoDeApu(
                codigo=resuelto.codigo,
                tipo=insumo.tipo,
                unidad=insumo.unidad,
                costo_unitario=insumo.costo_unitario,
                rendimiento=insumo.rendimiento,
            )
            for insumo, resuelto in zip(concepto.insumos, resueltos, strict=True)
            if insumo.tipo == TipoInsumo.MATERIAL
        ),
        cargos=tuple(CargoDeApu(tipo=c.tipo, importe=c.importe) for c in concepto.cargos),
    )


def _armar_plan(
    validados: Sequence[_ConceptoValidado],
    tipo_por_nombre: Mapping[str, UUID],
    resueltos_por_hoja: Mapping[str, tuple[InsumoRegistrado, ...]],
    insumos_nuevos: tuple[InsumoNuevo, ...],
    explosion: ExplosionCalculada,
    nuevo_id: Callable[[], UUID],
) -> PlanMaterializacion:
    jerarquia = _armar_jerarquia(validados, tipo_por_nombre, nuevo_id)
    conceptos = _armar_conceptos(validados, nuevo_id)
    concepto_id_por_codigo = {concepto.codigo: concepto.id for concepto in conceptos}
    partidas_concepto = _armar_partidas_concepto(
        validados, concepto_id_por_codigo, jerarquia.partida_id_por_clave, nuevo_id
    )
    return PlanMaterializacion(
        niveles=jerarquia.niveles,
        areas=jerarquia.areas,
        partidas=jerarquia.partidas,
        conceptos=conceptos,
        partidas_concepto=partidas_concepto,
        insumos_insertar=insumos_nuevos,
        apus=_armar_apus(validados, resueltos_por_hoja, concepto_id_por_codigo, nuevo_id),
        importe_venta=sumar((p.importe for p in partidas_concepto), Dinero),
        explosion=explosion,
    )


def _armar_jerarquia(
    validados: Sequence[_ConceptoValidado],
    tipo_por_nombre: Mapping[str, UUID],
    nuevo_id: Callable[[], UUID],
) -> _Jerarquia:
    """Niveles, áreas y partidas en el orden del catálogo: por la fila de cada nodo.

    Solo se crean los nodos que alcanza algún concepto. `nivel.orden` es la posición del nivel y
    `partida.orden`, la posición de la partida dentro de su área, ambas desde 1.
    """
    ubicaciones = {c.ubicacion.clave_partida: c.ubicacion for c in validados}
    niveles: list[NivelNuevo] = []
    areas: list[AreaNueva] = []
    partidas: list[PartidaNueva] = []
    nivel_id_por_fila: dict[int, UUID] = {}
    area_id_por_clave: dict[tuple[int, int], UUID] = {}
    partida_id_por_clave: dict[tuple[int, int, int], UUID] = {}
    orden_en_area: dict[tuple[int, int], int] = {}

    for clave in sorted(ubicaciones):
        ubicacion = ubicaciones[clave]
        if ubicacion.fila_nivel not in nivel_id_por_fila:
            nivel = NivelNuevo(id=nuevo_id(), nombre=ubicacion.nombre_nivel, orden=len(niveles) + 1)
            niveles.append(nivel)
            nivel_id_por_fila[ubicacion.fila_nivel] = nivel.id
        if ubicacion.clave_area not in area_id_por_clave:
            area = AreaNueva(
                id=nuevo_id(),
                nivel_id=nivel_id_por_fila[ubicacion.fila_nivel],
                nombre=ubicacion.nombre_area,
            )
            areas.append(area)
            area_id_por_clave[ubicacion.clave_area] = area.id
        orden_en_area[ubicacion.clave_area] = orden_en_area.get(ubicacion.clave_area, 0) + 1
        partida = PartidaNueva(
            id=nuevo_id(),
            area_id=area_id_por_clave[ubicacion.clave_area],
            tipo_partida_id=tipo_por_nombre[ubicacion.nombre_asignable],
            orden=orden_en_area[ubicacion.clave_area],
        )
        partidas.append(partida)
        partida_id_por_clave[clave] = partida.id

    return _Jerarquia(
        niveles=tuple(niveles),
        areas=tuple(areas),
        partidas=tuple(partidas),
        partida_id_por_clave=partida_id_por_clave,
    )


def _armar_conceptos(
    validados: Sequence[_ConceptoValidado],
    nuevo_id: Callable[[], UUID],
) -> tuple[ConceptoNuevo, ...]:
    """Un `ConceptoNuevo` por código, con la descripción y la unidad de su primera aparición."""
    primeras: dict[str, _ConceptoValidado] = {}
    for concepto in validados:
        primeras.setdefault(concepto.codigo, concepto)
    return tuple(
        ConceptoNuevo(
            id=nuevo_id(),
            codigo=codigo,
            descripcion=primera.descripcion,
            unidad=primera.unidad,
        )
        for codigo, primera in primeras.items()
    )


def _armar_partidas_concepto(
    validados: Sequence[_ConceptoValidado],
    concepto_id_por_codigo: Mapping[str, UUID],
    partida_id_por_clave: Mapping[tuple[int, int, int], UUID],
    nuevo_id: Callable[[], UUID],
) -> tuple[PartidaConceptoNueva, ...]:
    return tuple(
        PartidaConceptoNueva(
            id=nuevo_id(),
            concepto_id=concepto_id_por_codigo[concepto.codigo],
            partida_id=partida_id_por_clave[concepto.ubicacion.clave_partida],
            cantidad=concepto.cantidad,
            precio_unitario=concepto.precio_unitario,
            importe=concepto.importe,
        )
        for concepto in validados
    )


def _armar_apus(
    validados: Sequence[_ConceptoValidado],
    resueltos_por_hoja: Mapping[str, tuple[InsumoRegistrado, ...]],
    concepto_id_por_codigo: Mapping[str, UUID],
    nuevo_id: Callable[[], UUID],
) -> tuple[ApuNuevo, ...]:
    """Un `ApuNuevo` por código de concepto (ADR 2026-11-05), el de su primera aparición."""
    apus: list[ApuNuevo] = []
    codigos_con_apu: set[str] = set()
    for concepto in validados:
        if concepto.codigo in codigos_con_apu:
            continue
        codigos_con_apu.add(concepto.codigo)
        apus.append(
            ApuNuevo(
                id=nuevo_id(),
                concepto_id=concepto_id_por_codigo[concepto.codigo],
                hoja=concepto.hoja,
                costo_material=concepto.costo_material,
                costo_mano_obra=concepto.costo_mano_obra,
                costo_directo=concepto.costo_directo,
                total_cargos=concepto.total_cargos,
                total_indirectos=concepto.total_indirectos,
                precio_unitario=concepto.precio_unitario,
                fecha_analisis=concepto.fecha_analisis,
                analista=concepto.analista,
                insumos=tuple(
                    ApuInsumoNuevo(
                        insumo_id=resuelto.id,
                        costo_unitario=insumo.costo_unitario,
                        rendimiento=insumo.rendimiento,
                        cargo=insumo.cargo,
                    )
                    for insumo, resuelto in zip(
                        concepto.insumos, resueltos_por_hoja[concepto.hoja], strict=True
                    )
                ),
                cargos=concepto.cargos,
            )
        )
    return tuple(apus)


__all__ = [
    "ApuCargoNuevo",
    "ApuInsumoNuevo",
    "ApuNuevo",
    "AreaNueva",
    "AsignacionInvalida",
    "ConceptoNuevo",
    "ExplosionRechazada",
    "InsumoEnConflicto",
    "InsumoNuevo",
    "InsumoRegistrado",
    "NivelNuevo",
    "PartidaConceptoNueva",
    "PartidaNueva",
    "PlanMaterializacion",
    "PreparacionInconsistente",
    "ResultadoMaterializacion",
    "planificar_materializacion",
]
