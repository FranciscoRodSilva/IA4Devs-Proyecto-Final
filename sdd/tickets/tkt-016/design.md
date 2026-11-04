# Design · TKT-016 · Cálculo de la explosión por tipo de partida

> [← index](_index.md) | [← spec](spec.md) | Siguiente: `impl.md` (lo escribe `/sdd-ejecutar`)

## Estrategia

Una sola función pura nueva, `calcular_explosion`, en `backend/cimenta/presupuesto/dominio/explosion.py`. Recibe los conceptos de la obra ya emparejados con su tipo de partida y su análisis leído, y devuelve la explosión agregada y los importes por tipo de partida con **precisión completa**, o un rechazo con todas sus causas. La salida que persistirá TKT-017 se obtiene con un método `cuantizar()` del resultado, el único punto donde se redondea (`M3`, `PA-23`). Los objetos que trae la lectura (`ConceptoLeido`, `AnalisisLeido`) se reutilizan tal cual. A `tipos_base` solo se le añaden dos cocientes con nombre, que el promedio ponderado necesita y que hoy no existen. Las pruebas de la regla construyen los objetos en memoria; las de `M5` pasan por los lectores reales de TKT-013 y TKT-014b sobre un libro sintético, y la reconciliación con `AP-058-25` queda tras variables de entorno y se omite con su motivo.

## Escalera de decisión

| Objeto | Peldaño donde paró | Por qué |
|---|---|---|
| `calcular_explosion` | 5 · objeto nuevo | Ninguna regla existente agrega insumos por tipo de partida; es el Must `M1` a `M4`. Sin equivalente nativo: el dominio no consulta la base |
| `ConceptoAExplotar` (entrada) | 5 · objeto nuevo, mínimo | Tres campos: `concepto: ConceptoLeido`, `tipo_partida_id: UUID \| None`, `analisis: AnalisisLeido \| None`. Reutiliza los objetos de lectura (peldaño 3) y solo añade el emparejamiento, que la decisión del 2026-11-03 exige recibir como entrada (`PA-16.1`) |
| `ConceptoLeido`, `AnalisisLeido`, `InsumoLeido`, `CargoLeido`, `TipoInsumo`, `TipoCargo` | 3 · reuso | Ya traen cantidad, precio unitario del pie, insumos con clave normalizada (ADR-035) y cargos tipados. No se modifican (`CA-R2`) |
| `RenglonExplosion`, `ImportesTipoPartida`, `ExplosionCalculada` | 5 · objetos nuevos | La salida no existe en ningún sitio. *Dataclasses* congeladas con `slots`, que dan la inmutabilidad de `CA-9` sin código adicional (peldaño 2, nativo de Python) |
| `MotivoRechazoExplosion`, `CausaRechazoExplosion`, `RechazoExplosion` | 5 · objetos nuevos | `M4` exige enumerar causas con código, fila y clave. `Hallazgo` de TKT-013 no sirve: describe una celda de hoja (`hoja`, `columna`, `valor_original`), no un concepto ni un tipo de partida, y su `CausaHallazgo` es el catálogo de la importación, que TKT-015 traduce a `ck_importacion_error_tipo`; mezclar causas de cálculo ahí ensancha ese catálogo sin necesidad |
| `RechazoRegla` de `contrato_error` | 1 · YAGNI, fuera | No hay caso de uso ni ruta (non-goal). El dominio devuelve; TKT-017 lanza |
| `cociente_rendimiento(cantidad: Cantidad, base: Cantidad) -> Rendimiento` en `tipos_base` | 4 · cambio mínimo | El rendimiento ponderado es `Σ(q × r) / Σ q`. Peldaño 3 descartado: `Cantidad / Cantidad` existe pero devuelve `Porcentaje` (escala 9,6, tres enteros), y reenvolver su `.valor` en `Rendimiento(...)` pasa por la heurística `_viene_de_float` del constructor y mezcla semánticas. Calcular con `Decimal` crudo en el dominio duplicaría el contexto `_DIVISION` de 28 dígitos (`PA-T6` de TKT-004). Se añade una función con nombre, no un operador, para no cambiar el resultado de `Cantidad / Cantidad` |
| `cociente_precio_unitario(importe: Dinero, cantidad: Cantidad) -> Dinero` en `tipos_base` | 4 · cambio mínimo | El costo ponderado es `Σ(q × r × c) / Σ(q × r)`. `Dinero ÷ Cantidad` no existe y la prueba `test_tkt004_ca04_division_entre_tipos_no_admitida_cruces_con_dinero_y_porcentaje` exige que el operador siga dando `TypeError` (`PA-T11`). Una función con nombre lo resuelve sin tocar esa prueba ni el álgebra de operadores; `PA-T15` de TKT-004 prevé añadir operaciones «con su escenario» |
| `Dinero × Rendimiento` | 1 · YAGNI, fuera | No hace falta: `(Cantidad × Rendimiento) × Dinero` ya da `Dinero` con los operadores existentes |
| Exponer la regla en `cimenta/presupuesto/interfaz.py` | 1 · YAGNI, fuera | TKT-017 la consume desde `presupuesto/aplicacion/`, el mismo módulo. Ningún otro módulo la necesita |
| Emparejar el libro leído con los conceptos (`conceptos_a_explotar`) | 3 · reuso, en soporte de pruebas | Lo necesitan `CA-8` y `CA-10`, no ningún Must de producción: vive en `backend/herramientas/soporte_tkt016.py`, junto a `soporte_tkt013.py` y `soporte_tkt014.py`. TKT-017 decidirá su versión de producción cuando exista `PA-T8` |
| Lector del archivo `AP-058-25 EXPLOSION DE INSUMOS` | **Pendiente de la persona dueña (P-1)** | Nadie ha medido la disposición de ese libro y no está en el repositorio. Ver «Preguntas para el gate» |
| Variable `CIMENTA_EXPLOSION_UNION` y su fixture | 4 · cambio mínimo | Reutiliza `_bytes_catalogo_real` de `backend/tests/conftest.py`, que ya omite con motivo |

Ningún objeto paró en el peldaño 4 tocando un invariante registrado: los dos cocientes añaden aritmética exacta de `Decimal` y no alteran la regla 1.

## Capas afectadas

### Dominio

| Archivo | Qué | Regla |
|---|---|---|
| `backend/tipos_base/numericos.py` | `cociente_rendimiento` y `cociente_precio_unitario`; `_cociente` se parte en `_dividir(a, b) -> Decimal` (comprobación de cero y `_DIVISION.divide`) y la envoltura en `Porcentaje`, sin cambiar su comportamiento | Regla 1; `PA-T6` |
| `backend/tipos_base/__init__.py` | Exporta los dos cocientes en `__all__` | — |
| `backend/cimenta/presupuesto/dominio/explosion.py` (nuevo) | Objetos de valor de entrada, salida y rechazo, y `calcular_explosion` | `RN-24`, `PA-01`, `PA-03`, `PA-23`; invariante 8 |

#### Firmas exactas

```python
# tipos_base/numericos.py
def cociente_rendimiento(cantidad: Cantidad, base: Cantidad) -> Rendimiento: ...
def cociente_precio_unitario(importe: Dinero, cantidad: Cantidad) -> Dinero: ...
```

Las dos comprueban `type(x) is Cantidad` (o `Dinero`) y lanzan `TypeError` si no; dividen con `_DIVISION` (28 dígitos significativos, `ROUND_HALF_UP` en el último) y lanzan `ZeroDivisionError` con el mismo mensaje de «regla 12» que `_cociente`. No cuantizan.

```python
# cimenta/presupuesto/dominio/explosion.py
from __future__ import annotations
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

class MotivoRechazoExplosion(StrEnum):
    SIN_TIPO_PARTIDA = "SIN_TIPO_PARTIDA"
    SIN_ANALISIS = "SIN_ANALISIS"
    CANTIDAD_AUSENTE = "CANTIDAD_AUSENTE"
    CANTIDAD_NO_POSITIVA = "CANTIDAD_NO_POSITIVA"
    SIN_PRECIO_UNITARIO = "SIN_PRECIO_UNITARIO"
    CARGO_AUSENTE = "CARGO_AUSENTE"
    CARGO_SIN_IMPORTE = "CARGO_SIN_IMPORTE"
    INSUMO_SIN_COSTO = "INSUMO_SIN_COSTO"
    RENDIMIENTO_AUSENTE = "RENDIMIENTO_AUSENTE"
    RENDIMIENTO_NO_POSITIVO = "RENDIMIENTO_NO_POSITIVO"
    UNIDAD_EN_CONFLICTO = "UNIDAD_EN_CONFLICTO"
    SUGERIDO_NEGATIVO = "SUGERIDO_NEGATIVO"

@dataclass(frozen=True, slots=True)
class ConceptoAExplotar:
    concepto: ConceptoLeido
    tipo_partida_id: UUID | None
    analisis: AnalisisLeido | None

@dataclass(frozen=True, slots=True)
class RenglonExplosion:
    tipo_partida_id: UUID
    clave_insumo: str
    cantidad_conceptos: Cantidad        # Σ cantidad de los conceptos que usan el insumo
    cantidad_presupuestada: Cantidad    # Σ cantidad × rendimiento
    rendimiento_congelado: Rendimiento  # RN-24 · cantidad_presupuestada / cantidad_conceptos
    costo_unitario: Dinero              # Σ(q × r × c) / cantidad_presupuestada
    importe: Dinero                     # Σ(q × r × c)
    def cuantizar(self) -> RenglonExplosion: ...

@dataclass(frozen=True, slots=True)
class ImportesTipoPartida:
    tipo_partida_id: UUID
    importe_venta: Dinero
    importe_sugerido: Dinero            # PA-03 · sugerencia, nunca tope

@dataclass(frozen=True, slots=True)
class ExplosionCalculada:
    renglones: tuple[RenglonExplosion, ...]
    importes: tuple[ImportesTipoPartida, ...]
    def cuantizar(self) -> ExplosionCalculada: ...

@dataclass(frozen=True, slots=True)
class CausaRechazoExplosion:
    motivo: MotivoRechazoExplosion
    codigo_concepto: str | None
    fila: int | None
    clave_insumo: str | None = None
    cargo: TipoCargo | None = None
    tipo_partida_id: UUID | None = None
    unidades: tuple[str, ...] = ()
    importe_sugerido: Dinero | None = None

@dataclass(frozen=True, slots=True)
class RechazoExplosion:
    causas: tuple[CausaRechazoExplosion, ...]

def calcular_explosion(
    conceptos: Sequence[ConceptoAExplotar],
) -> ExplosionCalculada | RechazoExplosion:
    """Implementa RN-24 (rendimiento congelado) y PA-01 (agregado por tipo de partida en
    toda la obra); importe sugerido de PA-03 y redondeo de PA-23. Sin efectos secundarios."""
```

El campo se llama `importe`, no `importe_venta`: vale cantidad × costo y es un costo (`PA-16.7`). TKT-017 decide la columna a la que lo lleva.

#### Algoritmo, paso a paso

Cada paso es una función privada con nombre; ninguna cuantiza.

1. **Causas por concepto** (`_causas_de_concepto`), en el orden de la entrada, y para cada concepto en este orden:
   1. `tipo_partida_id is None` → `SIN_TIPO_PARTIDA`.
   2. `concepto.cantidad is None` → `CANTIDAD_AUSENTE`; si no, `concepto.cantidad.valor <= 0` → `CANTIDAD_NO_POSITIVA`.
   3. `analisis is None` → `SIN_ANALISIS`, y se salta el resto de este concepto.
   4. `analisis.precio_unitario is None` → `SIN_PRECIO_UNITARIO`. Se usa **el precio del pie del análisis** (`AnalisisLeido.precio_unitario`), que TKT-014b cuadra contra sus totales; ni el de la cabecera, que en ENITI trae `#REF!`, ni el del catálogo (`PA-16.8`).
   5. Para `UTILIDAD` y después `INDIRECTOS`: los cargos de ese `tipo`; si no hay ninguno → `CARGO_AUSENTE` con `cargo=<tipo>`; si alguno tiene `importe is None` → `CARGO_SIN_IMPORTE` con `cargo=<tipo>`. Nunca se toma un cargo ausente como cero.
   6. Por cada insumo con `tipo == TipoInsumo.MATERIAL`, en su orden: `costo_unitario is None` → `INSUMO_SIN_COSTO`; `rendimiento is None` → `RENDIMIENTO_AUSENTE`; si no, `rendimiento.valor <= 0` → `RENDIMIENTO_NO_POSITIVO`. Cada causa lleva `clave_insumo`. Un mismo insumo puede dar causa de costo y de rendimiento a la vez. Los insumos `MANO_OBRA` no se revisan (`CA-3`, `PA-16.4`).
   Toda causa de este paso lleva `codigo_concepto=concepto.codigo` y `fila=concepto.fila`.
2. **Causas de unidad** (`_causas_de_unidad`): sobre los insumos `MATERIAL` de los conceptos con análisis y con `unidad is not None`, se agrupan las unidades por `clave`. Por cada clave con más de una unidad, se emite una causa `UNIDAD_EN_CONFLICTO` **por cada ocurrencia** (concepto e insumo), en el orden de la entrada, con `clave_insumo`, `unidades=tuple(sorted(unidades))`, y el código y la fila del concepto. Se replica el criterio de `proponer_insumos` de TKT-014b, que también ignora la unidad ausente (ver `P-5`).
3. **Causas de sugerido** (`_causas_de_sugerido`): solo para los tipos de partida en los que **ningún** concepto tiene causa de los pasos 1.2 a 1.5 (cantidad, análisis, precio o cargos), porque sin esos datos el sugerido no está definido. Para cada uno, `sugerido = sumar(q × (pu − Σ utilidad − Σ indirectos))`, y si `sugerido.valor < 0` → `SUGERIDO_NEGATIVO` con `tipo_partida_id` y `importe_sugerido=sugerido` sin cuantizar. Los tipos se recorren ordenados por `str(tipo_partida_id)`. Este paso se ejecuta aunque los pasos 1 y 2 hayan dado causas: el rechazo enumera todas.
4. Si hay alguna causa → `RechazoExplosion(causas=paso1 + paso2 + paso3)`, sin renglones ni importes (todo o nada).
5. **Agregación** (`_agregar`): por cada concepto (por su posición en la entrada) y cada insumo `MATERIAL` de su análisis, con clave `(tipo_partida_id, clave)`:
   - `q_r = concepto.cantidad * insumo.rendimiento` (`Cantidad`), y se acumula en la cantidad presupuestada.
   - `q_r * insumo.costo_unitario` (`Dinero`) se acumula en el importe.
   - La posición del concepto se añade a un conjunto; `cantidad_conceptos` es la suma de las cantidades de esos conceptos, **cada concepto una sola vez** aunque su análisis liste la misma clave en dos renglones.
   - `rendimiento_congelado = cociente_rendimiento(cantidad_presupuestada, cantidad_conceptos)` y `costo_unitario = cociente_precio_unitario(importe, cantidad_presupuestada)`.
   - El importe es `Σ(q × r × c)`, igual en aritmética exacta a `cantidad_presupuestada × costo_unitario` de `M1`, pero sin pasar por la división: así `CA-2` da `27100.0000` exacto.
   - Renglones ordenados por `(str(tipo_partida_id), clave_insumo)`.
6. **Importes por tipo** (`_importes`): `importe_venta = sumar(q × pu)` y `importe_sugerido` el del paso 3, ordenados por `str(tipo_partida_id)`. Solo aparecen los tipos presentes en la entrada.
7. `cuantizar()` devuelve una copia con cada cifra en su escala: `Cantidad` a 4, `Rendimiento` a 6, `Dinero` a 4. Es el único redondeo. TKT-017 persiste `explosion.cuantizar()`.

**Entrada vacía:** devuelve `ExplosionCalculada((), ())`. Que una obra sin conceptos no llegue al congelado es de TKT-015 y TKT-017.

**Cómo se lee la última línea de `CA-2`.** «Rendimiento congelado × Σ cantidad reproduce la cantidad presupuestada sin diferencia» se comprueba con el rendimiento de precisión completa y la comparación en la escala de la columna: `(r.rendimiento_congelado * r.cantidad_conceptos).cuantizar() == r.cantidad_presupuestada.cuantizar()`. Con el rendimiento ya cuantizado la identidad es imposible en general: `1.083333 × 300 = 324.9999`, no `325`. No es una decisión nueva, es la única lectura aritméticamente posible del criterio con `M3`.

## Orden de implementación

Se ejecuta fila por fila con el ciclo TDD de [metodología §16](../../metodologia.md#16--el-ciclo-tdd): `tester-backend` escribe en rojo los tests de la fila, el desarrollador los pone en verde de uno en uno, y la verificación corre antes de pasar a la siguiente. Todos los comandos se ejecutan desde `backend/`. El modelo de la columna es el del desarrollador; `tester-backend` va siempre en `sonnet`.

En las filas A4 y A5 el rojo válido es «el rechazo no ocurre»: con el código de A2 y A3, un dato ausente produce un `TypeError` o `AttributeError` al operar con `None`, o un `ExplosionCalculada` donde se esperaba un `RechazoExplosion`. Los nombres que todavía no existen (`RechazoExplosion`, `MotivoRechazoExplosion`) dan un rojo por «no existe», que también es válido.

Las filas se agrupan en dos partes por la propuesta de partición (ver «Tamaño y partición»). Si la persona dueña no la acepta, se ejecutan en el mismo orden en un solo ticket.

| # | Paso | Tests que pone en verde | Agente | Modelo | Verificación | Estado |
|---|---|---|---|---|---|---|
| A0 | Línea base de herramientas (E-1). Sin código | — | `tester-backend` | `haiku` · tarea mecánica: los comandos y el resultado esperado están escritos aquí | `uv run ruff check .`, `uv run mypy .`, `uv run lint-imports`, `uv run python -m herramientas.verificar_float` y `uv run pytest tests/test_tipos_base_aritmetica.py tests/test_tipos_base_redondeo.py tests/test_tkt013_dominio.py tests/test_tkt014_hoja.py tests/test_tkt014_asociacion.py tests/test_tkt014_lector.py -q`, todos en verde, con la salida en `impl.md`. Si alguno falla antes de tocar nada, `/sdd-escalar` | Pendiente |
| A1 | `cociente_rendimiento` y `cociente_precio_unitario` en `tipos_base`, partiendo `_cociente` en `_dividir` más la envoltura. ~25 líneas de código y ~50 de prueba en `tests/test_tkt016_cocientes.py` | TC-01 a TC-04 | `tester-backend` → `desarrollador-dominio` | `sonnet` · disparador: regla de dinero, aritmética compartida que usarán `RN-03` (TKT-020) y el semáforo (TKT-039) | `uv run pytest tests/test_tkt016_cocientes.py tests/test_tipos_base_aritmetica.py -q` en verde, y `uv run python -m herramientas.verificar_float` | Pendiente |
| A2 | `explosion.py`: `ConceptoAExplotar`, `RenglonExplosion`, `ExplosionCalculada` (con `importes=()` hasta A3) y los pasos 5 y 7 del algoritmo, sin validación. `ImportesTipoPartida` nace en A3. Ayudantes de prueba en `herramientas/soporte_tkt016.py`: `concepto(...)`, `analisis(...)`, `insumo_material(...)`, `insumo_mano_obra(...)`, `cargo(...)` y las constantes `MUROS` y `PLAFONES` (UUID fijos). ~110 líneas de código, ~60 de soporte y ~70 de prueba en `tests/test_tkt016_explosion.py` | TC-05 a TC-08 | `tester-backend` → `desarrollador-dominio` | `sonnet` · disparador: regla de dinero (costo ponderado e importe) que produce la cantidad presupuestada contra la que evalúa `RN-03` | `uv run pytest tests/test_tkt016_explosion.py -k "agrega or ponderados or solo_material or una_vez" -q` en verde | Pendiente |
| A3 | `ImportesTipoPartida` con `importe_venta` e `importe_sugerido` (paso 6, y la suma del paso 3 sin la comprobación de signo) y `cuantizar()` completo. ~45 líneas de código, ~70 de prueba | TC-09 a TC-12 | `tester-backend` → `desarrollador-dominio` | `sonnet` · disparador: regla de dinero y modo de redondeo (`PA-23`) | `uv run pytest tests/test_tkt016_explosion.py -q` en verde | Pendiente |
| A4 | `MotivoRechazoExplosion`, `CausaRechazoExplosion`, `RechazoExplosion` y el paso 1.1 a 1.5 con el corte del paso 4. ~60 líneas de código, ~70 de prueba en `tests/test_tkt016_rechazos.py` | TC-13 a TC-15 | `tester-backend` → `desarrollador-dominio` | `haiku` | `uv run pytest tests/test_tkt016_rechazos.py -k "incompletos or negativa or sin_precio" -q` y `uv run pytest tests/test_tkt016_explosion.py -q`, ambos en verde | Pendiente |
| A5 | Paso 1.6, paso 2 y la comprobación de signo del paso 3. ~60 líneas de código, ~90 de prueba | TC-16 a TC-20 | `tester-backend` → `desarrollador-dominio` | `sonnet` · disparador: límite de importe (invariante 8, sugerido no negativo) sobre dinero, afín a `RN-03` | `uv run pytest tests/test_tkt016_rechazos.py tests/test_tkt016_explosion.py -q` en verde | Pendiente |
| A6 | Pruebas de inmutabilidad y de pureza. Sin código de producción: si nacen en verde, se investiga que afirmen lo que dicen (un mutante que quite `frozen=True` debe ponerlas en rojo). ~45 líneas de prueba en `tests/test_tkt016_fronteras.py` | TC-21, TC-22, TC-23 | `tester-backend` | `sonnet` · valor por omisión del agente | `uv run pytest tests/test_tkt016_fronteras.py -q`; `uv run lint-imports`; `uv run python -m herramientas.verificar_float`; `uv run ruff check .`; `uv run mypy .`; la regresión de TC-23 | Pendiente |
| A7 | Documentación de la parte a: arquitectura §7.4, PRD (`PA-23` cerrada), modelo de datos y ADR-036 si se aprueba (ver «Documentación afectada»). Sin código | — | `desarrollador-dominio` | `haiku` | `python tools/verificar_docs.py`; `python tools/extraer_mermaid.py`; `python -m unittest discover -s tools/tests -v` | Pendiente |
| A8 | Cierre de la parte a: mutantes M-1 a M-15 de las filas A1 a A5, uno por uno, cada uno revertido | Todos los de A1 a A6 | `tester-backend` | `sonnet` · valor por omisión del agente | Cada mutante pone en rojo el test que dice la tabla de mutación; tras revertir, `uv run pytest -q` completo en verde (requiere Docker en marcha) | Pendiente |
| B1 | Libro sintético de `CA-8` en `herramientas/soporte_tkt016.py`: `libro_explosion_sintetico(libro)` y `conceptos_a_explotar(libro_leido, tipo_por_fila)`. Sin código de producción. ~70 líneas de soporte y ~50 de prueba en `tests/test_tkt016_libro_sintetico.py` | TC-24, TC-25 | `tester-backend` | `sonnet` · valor por omisión del agente | `uv run pytest tests/test_tkt016_libro_sintetico.py -q` en verde. Si TC-24 falla por una cifra, se revisa primero el libro y el cálculo a mano de esta tabla, nunca la regla | Pendiente |
| B2 | Reconciliación de `CA-10` en `tests/test_tkt016_archivo_real.py` y la fixture `oraculo_explosion_union` en `conftest.py`. **Se escribe según la opción que elija la persona dueña en `P-1`**; la fila describe la recomendada. ~15 líneas de fixture y ~60 de prueba | TC-26, TC-27 | `tester-backend` | `sonnet` · valor por omisión del agente | `uv run pytest tests/test_tkt016_archivo_real.py -q -ra`: sin variables, TC-26 aparece `SKIPPED` con el motivo y TC-27 en verde. Con las variables y el libro de Union de hoy, TC-26 aparece `SKIPPED` por `PA-T3` (cero asociaciones). La salida va a `impl.md` | Pendiente |
| B3 | Documentación de la parte b: `docs/arranque-local.md` con `CIMENTA_EXPLOSION_UNION`. Sin código | — | `desarrollador-dominio` | `haiku` | `python tools/verificar_docs.py` | Pendiente |
| B4 | Cierre: suite completa y comprobaciones del trabajo `backend` de `ci.yml` en local | Todos | `tester-backend` | `sonnet` · valor por omisión del agente | `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy .`, `uv run lint-imports`, `uv run python -m herramientas.verificar_float`, `uv run pytest -q -ra` (Docker en marcha) | Pendiente |

**Modelo:** `haiku` por omisión; `sonnet` solo donde la fila cita un disparador de [metodología §14](../../metodologia.md#14--enrutamiento-de-modelo). Las filas que ejecuta solo `tester-backend` llevan su valor por omisión. Ninguna fila va en `opus`.

Estado: `Pendiente` · `✓ Hecho` · `⚠ Ajustado` (y el ajuste se documenta en `impl.md`).

### Tamaño y partición

| Parte | Filas | Código de producción | Pruebas y soporte | Documentación |
|---|---|---|---|---|
| a · la regla | A0 a A8 | ~300 | ~455 | ~60, más ADR-036 (~60) |
| b · `M5` sobre los lectores y el archivo real | B1 a B4 | 0 | ~195 | ~10 |
| **Total** | | **~300** | **~650** | **~130** |

El total ronda las 1,080 líneas, muy por encima de las ~400. El código de producción solo (~300) cabe, pero las pruebas de rechazo de `M4` y el libro de `M5` lo duplican. **Propuesta (`P-3`):** partir en **TKT-016a** (filas A0 a A8: la regla completa con `M1` a `M4`, sus rechazos, `CA-9`, `CA-R1`, `CA-R2` y el cierre de `PA-23`) y **TKT-016b** (filas B1 a B4: `CA-8` y `CA-10`). La parte a entrega por sí sola una regla verificable con todos sus rechazos; la b no añade código de producción, solo evidencia contra los lectores y el archivo real. Ninguna de las dos deja una regla sin su escenario de rechazo.

## Plan de pruebas

Todos son de `dominio/`: pytest puro, sin base ni Docker, salvo la suite completa de A8 y B4. Los importes se construyen desde cadena. Los ayudantes de `soporte_tkt016.py` crean `ConceptoLeido` con `Ruta` explícita (el área y el nivel solo cambian en TC-05) y `AnalisisLeido` con `hallazgos=()` y totales en `None`, que la regla no lee.

**Análisis por omisión de los ayudantes:** precio unitario `641.36`, cargos `INDIRECTOS 60.00`, `UTILIDAD 50.00` e `IVA 40.00`, sin insumos salvo los que pide cada caso. Cada caso de rechazo parte de conceptos válidos y estropea **un solo dato** por concepto, para que la tupla de causas sea exacta.

| # | Caso | Tipo | Criterio que cubre | Escenario |
|---|---|---|---|---|
| TC-01 | `test_hdu001_esc14_cociente_rendimiento_da_rendimiento_con_28_digitos`: `cociente_rendimiento(Cantidad("3"), Cantidad("2"))` es `Rendimiento` con valor `1.5`; `cociente_rendimiento(Cantidad("30"), Cantidad("14"))` tiene 28 dígitos significativos y su `cuantizar()` es `Rendimiento("2.142857")` | feliz | `CA-2`, `M3` | `HDU-001 esc. 14` |
| TC-02 | `test_hdu001_esc14_cociente_precio_unitario_da_dinero`: `cociente_precio_unitario(Dinero("27100"), Cantidad("325"))` es `Dinero` y su `cuantizar()` es `Dinero("83.3846")`; `cociente_precio_unitario(Dinero("10"), Cantidad("4")).valor == Decimal("2.5")` | feliz | `CA-2` | `HDU-001 esc. 14` |
| TC-03 | `test_hdu001_esc14_cociente_entre_cero_falla`, parametrizado con los dos cocientes y divisor `0` y `0.0000`: `ZeroDivisionError` que menciona «regla 12» | **rechazo** | `CA-7` («ninguna división por cero») | `HDU-001 esc. 14` |
| TC-04 | `test_hdu001_esc14_cociente_rechaza_tipos_ajenos`: un `Dinero` donde va `Cantidad`, un `Rendimiento` donde va `Dinero`: `TypeError`. Y `Dinero("1") / Cantidad("1")` sigue dando `TypeError` (`PA-T11`) | **rechazo** | `CA-R1` | `HDU-001 esc. 14` |
| TC-05 | `test_hdu001_esc14_agrega_por_tipo_de_partida_en_toda_la_obra`: los datos de `CA-1` (MURO-A, Área 1, `100`, PANEL `1.05` a `80.00`; MURO-B, Área 2, `200`, PANEL `1.10` a `85.00`, los dos en `MUROS`). Un solo renglón `(MUROS, "PANEL")` con `cantidad_presupuestada == Cantidad("325")` | feliz | `CA-1` | `HDU-001 esc. 14` |
| TC-06 | `test_hdu001_esc14_rendimiento_y_costo_ponderados`: con los datos de TC-05, el renglón cuantizado tiene `rendimiento_congelado == Rendimiento("1.083333")`, `costo_unitario == Dinero("83.3846")` e `importe == Dinero("27100.0000")`; sin cuantizar, `importe.valor == Decimal("27100")` exacto y `(rendimiento_congelado * cantidad_conceptos).cuantizar() == Cantidad("325.0000")` | feliz | `CA-2` | `HDU-001 esc. 14` |
| TC-07 | `test_hdu001_esc14_solo_material_entra_en_la_explosion`: un análisis con `PANEL` `MATERIAL` y `CUADRILLA` `MANO_OBRA` **sin rendimiento ni costo**. Resultado `ExplosionCalculada`, con una sola clave, `PANEL` | feliz y borde | `CA-3` | `HDU-001 esc. 14` |
| TC-08 | `test_hdu001_esc14_concepto_cuenta_una_vez_por_insumo`: un concepto de cantidad `10` cuyo análisis lista `PANEL` dos veces, con rendimiento `1` y `0.5`. `cantidad_presupuestada == 15`, `cantidad_conceptos == 10`, `rendimiento_congelado == 1.5` | borde | `CA-2` | `HDU-001 esc. 14` |
| TC-09 | `test_hdu001_esc15_importe_de_venta_y_sugerido_desde_el_analisis`, parametrizado con el precio unitario del catálogo en `999.99` y en `None`: concepto `MUROS` de cantidad `100`, análisis de `641.36` con `INDIRECTOS 60.00`, `UTILIDAD 50.00` e `IVA 40.00`. Cuantizado: `importe_venta == Dinero("64136.0000")` e `importe_sugerido == Dinero("53136.0000")` en los dos casos | feliz | `CA-4` | `HDU-001 esc. 15` |
| TC-10 | `test_hdu001_esc15_sugerido_es_sugerencia_sin_tope`: los nombres de los campos de `ImportesTipoPartida` son exactamente `{"tipo_partida_id", "importe_venta", "importe_sugerido"}` | feliz | `CA-4` | `HDU-001 esc. 15` |
| TC-11 | `test_hdu001_esc14_sin_redondeo_intermedio`: cinco conceptos de `MUROS` de cantidad `1`, cada uno con análisis de precio unitario `10.00005`, `UTILIDAD 0` e `INDIRECTOS 0`, y el insumo `X` con rendimiento `0.000050` y costo `10`. Cuantizado: `cantidad_presupuestada == Cantidad("0.0003")` (redondear cada producto daría `0.0005`; `ROUND_HALF_EVEN`, `0.0002`), `rendimiento_congelado == Rendimiento("0.000050")`, `importe_venta == Dinero("50.0003")` (por producto, `50.0005`; `HALF_EVEN`, `50.0002`). Sin cuantizar, `cantidad_presupuestada.valor == Decimal("0.00025")` | feliz y borde | `CA-5`, `PA-23` | `HDU-001 esc. 14` |
| TC-12 | `test_hdu001_esc14_cuantizar_lleva_cada_cifra_a_su_escala`: tras `cuantizar()`, el exponente de cantidad es `-4`, de rendimiento `-6`, de costo, importe, venta y sugerido `-4`; antes, el rendimiento de `30 / 14` tiene 28 dígitos significativos | feliz | `CA-5` | `HDU-001 esc. 14` |
| TC-13 | `test_hdu001_esc14_rechaza_conceptos_incompletos_con_todas_sus_causas`: MURO-OK válido en la fila 10; MURO-X sin tipo en la fila 12; PLAF-Y sin análisis en la fila 30; PLAF-Z sin cantidad en la fila 31; PLAF-W con cantidad `0` en la fila 32. Resultado `RechazoExplosion` cuyas `causas` son exactamente `(SIN_TIPO_PARTIDA, "MURO-X", 12)`, `(SIN_ANALISIS, "PLAF-Y", 30)`, `(CANTIDAD_AUSENTE, "PLAF-Z", 31)`, `(CANTIDAD_NO_POSITIVA, "PLAF-W", 32)`, en ese orden; el objeto no tiene `renglones` ni `importes` | **rechazo** | `CA-6` esc. 1, `M4` | `HDU-001 esc. 14` |
| TC-14 | `test_hdu001_esc14_rechaza_cantidad_negativa`: un concepto con cantidad `-1` da una causa `CANTIDAD_NO_POSITIVA` | **rechazo** | `CA-6`, `PA-16.10` | `HDU-001 esc. 14` |
| TC-15 | `test_hdu001_esc15_rechaza_analisis_sin_precio_o_sin_cargos`: MURO-A con análisis sin precio unitario; MURO-B con análisis sin cargo `UTILIDAD`; PLAF-C con `INDIRECTOS` sin importe. Causas exactas: `(SIN_PRECIO_UNITARIO, "MURO-A", fila)`, `(CARGO_AUSENTE, "MURO-B", fila, cargo=UTILIDAD)`, `(CARGO_SIN_IMPORTE, "PLAF-C", fila, cargo=INDIRECTOS)` | **rechazo** | `CA-6` esc. 2, `PA-16.9` | `HDU-001 esc. 15` |
| TC-16 | `test_hdu001_esc14_rechaza_insumos_sin_rendimiento_o_sin_costo`: MURO-A con `PANEL` sin rendimiento; MURO-B con `TORNILLO` sin costo; MURO-C con `CINTA` de rendimiento `0`. Tres causas exactas con código, fila y clave, y la llamada no lanza `ZeroDivisionError`. Parametrizado también con `CINTA` de rendimiento `-0.5` | **rechazo** | `CA-7` esc. 1, `PA-16.10` | `HDU-001 esc. 14` |
| TC-17 | `test_hdu001_esc14_rechaza_la_misma_clave_con_dos_unidades`: dos conceptos con `PANEL` en `M2` y en `PZA`. Dos causas `UNIDAD_EN_CONFLICTO`, una por concepto, con `clave_insumo == "PANEL"` y `unidades == ("M2", "PZA")` | **rechazo** | `CA-7` esc. 2, `PA-16.11` | `HDU-001 esc. 14` |
| TC-18 | `test_hdu001_esc15_rechaza_sugerido_negativo`: un concepto `MUROS` de cantidad `10`, precio `100.00`, `UTILIDAD 70.00` e `INDIRECTOS 40.00`. Una causa `SUGERIDO_NEGATIVO` con `tipo_partida_id == MUROS` e `importe_sugerido == Dinero("-100")` | **rechazo** | `CA-7` esc. 3, invariante 8 | `HDU-001 esc. 15` |
| TC-19 | `test_hdu001_esc15_sugerido_cero_se_acepta`: precio `100.00`, `UTILIDAD 60.00` e `INDIRECTOS 40.00`. Resultado `ExplosionCalculada` con `importe_sugerido == Dinero("0.0000")` tras cuantizar | borde | `CA-7` esc. 3 | `HDU-001 esc. 15` |
| TC-20 | `test_hdu001_esc15_sugerido_negativo_se_enumera_con_otras_causas`: los datos de TC-18 más un concepto `PLAFONES` válido salvo un insumo sin costo. Dos causas: `INSUMO_SIN_COSTO` y `SUGERIDO_NEGATIVO`, en ese orden | **rechazo** | `M4` | `HDU-001 esc. 15` |
| TC-21 | `test_hdu001_esc14_renglon_inmutable_sin_rendimiento_observado`: asignar `rendimiento_congelado` en un renglón lanza `dataclasses.FrozenInstanceError` y el valor no cambia; ningún campo de `RenglonExplosion` ni parámetro de `calcular_explosion` contiene «observado» | **rechazo** | `CA-9`, invariante 19 | `HDU-001 esc. 14` |
| TC-22 | `test_hdu001_esc14_regla_solo_importa_biblioteca_estandar_y_tipos_base`: el AST de `explosion.py` solo importa `__future__`, `collections.abc`, `dataclasses`, `enum`, `uuid`, `tipos_base` y `cimenta.presupuesto.dominio.*`; ningún `datetime`, `os`, `io`, `pathlib`, `socket` ni `random` | regresión | `CA-R1` | `HDU-001 esc. 14` |
| TC-23 | Regresión sin test nuevo: las suites `tests/test_tkt013_*.py`, `tests/test_tkt014_*.py` y `tests/test_tipos_base_*.py` en verde sin tocarlas, y `git diff --stat Produccion -- backend/tests/test_tkt013_*.py backend/tests/test_tkt014_*.py backend/tests/test_tipos_base_*.py ':!backend/tests/test_tipos_base_redondeo.py' backend/herramientas/soporte_tkt013.py backend/herramientas/soporte_tkt014.py backend/cimenta/presupuesto/dominio/catalogo.py backend/cimenta/presupuesto/dominio/analisis.py backend/cimenta/presupuesto/dominio/lectura_*.py backend/cimenta/presupuesto/dominio/asociacion_analisis.py backend/cimenta/presupuesto/infraestructura/` vacío | regresión de invariante | `CA-R2` | — |
| TC-24 | `test_hdu001_esc14_libro_sintetico_reproduce_su_total`: el libro de la tabla siguiente, leído con `leer_libro_presupuesto_bytes`, emparejado con `conceptos_a_explotar` y calculado. Tras cuantizar: cinco renglones con las cifras exactas de la tabla, `sumar` de sus importes `== Dinero("773.7000")`, e importes por tipo `MUROS` `2389.3000` / `2028.7300` y `PLAFONES` `1748.2300` / `1464.9250` | feliz | `CA-8` | `HDU-001 esc. 14` |
| TC-25 | `test_hdu001_esc14_mismo_insumo_en_dos_tipos_da_dos_filas`: en el resultado de TC-24, `MATERIAL UNO` y `MATERIAL DOS` aparecen una vez en `MUROS` y otra en `PLAFONES`, y `CUADRILLA X` no aparece | feliz | `CA-8`, `CA-3` | `HDU-001 esc. 14` |
| TC-26 | `test_hdu001_esc14_reconcilia_con_la_explosion_real` (forma según `P-1`) | feliz | `CA-10` esc. 1 | `HDU-001 esc. 14` |
| TC-27 | `test_hdu001_esc14_sin_variable_la_reconciliacion_se_omite`: con `monkeypatch.delenv("CIMENTA_EXPLOSION_UNION", raising=False)`, la carga del oráculo lanza `pytest.skip.Exception` cuyo mensaje nombra la variable | **rechazo** | `CA-10` esc. 2 | `HDU-001 esc. 14` |

**Concurrencia:** no aplica. La regla no toma bloqueos ni escribe; el bloqueo pesimista de `RN-03` es de TKT-020.

### Libro sintético de `CA-8`

Se construye con `LibroCatalogo` (fixture `libro_catalogo`) y los ayudantes de TKT-013 y TKT-014, en el mismo orden que `libro_eniti_con_apu_y_resumen`: primero las tres hojas de análisis con `escribir_hoja_apu_sintetica`, después la hoja `HOJA_ENITI` con `metadatos_siete_filas`, `encabezado_eniti` y las filas 9 a 12 de nodos (`RAIZ SYN`, `NIVEL A`, `ZONA 1`, `TRABAJO X`).

| Hoja | Código | Variantes de `hoja_apu_sintetica` | Insumos `MATERIAL` resultantes |
|---|---|---|---|
| `APU-A` | `A-01` | ninguna (pie `158.93`) | `MATERIAL UNO` PZA, costo `10`, rend. `2`; `MATERIAL DOS` KG, costo `5`, rend. `1.5` |
| `APU-B` | `B-01` | `pie=Decimal("200")`; `celdas_rotas={(8,"E"): Decimal("12"), (8,"F"): Decimal("2.5"), (9,"A"): "MATERIAL TRES", (9,"E"): Decimal("7"), (9,"F"): Decimal("0.4")}` | `MATERIAL UNO` PZA, `12`, `2.5`; `MATERIAL TRES` KG, `7`, `0.4` |
| `APU-C` | `C-01` | `celdas_rotas={(8,"E"): Decimal("11"), (8,"F"): Decimal("3")}` | `MATERIAL UNO` PZA, `11`, `3`; `MATERIAL DOS` KG, `5`, `1.5` |

Las tres conservan `CUADRILLA X` (`MANO_OBRA`), `INDIRECTOS 10.302` y `UTILIDAD 15.453` de la plantilla. Al cambiar costos, el lector marcará `PU_NO_CUADRA` en `APU-B` y `APU-C`; es un hallazgo, no anula el precio del pie, y la regla no lee hallazgos.

Conceptos del catálogo, columnas `(código, descripción, unidad, cantidad, P.U., importe)`, y tipo asignado por fila en `tipo_por_fila`:

| Fila | Código | Cantidad | P.U. del catálogo | Tipo |
|---|---|---|---|---|
| 13 | `A-01` | `10` | `1` | `MUROS` |
| 14 | `B-01` | `4` | `1` | `MUROS` |
| 15 | `A-01` | `6` | `1` | `PLAFONES` |
| 16 | `C-01` | `5` | `1` | `PLAFONES` |

El P.U. del catálogo vale `1` a propósito: si la regla lo usara, la venta saldría en `14` y `11`.

Resultado calculado a mano:

| Tipo | Clave | Σ q × r | Σ q | Rend. (6) | Importe | Costo (4) |
|---|---|---|---|---|---|---|
| `MUROS` | `MATERIAL DOS` | `15` | `10` | `1.500000` | `75.0000` | `5.0000` |
| `MUROS` | `MATERIAL TRES` | `1.6` | `4` | `0.400000` | `11.2000` | `7.0000` |
| `MUROS` | `MATERIAL UNO` | `30` | `14` | `2.142857` | `320.0000` | `10.6667` |
| `PLAFONES` | `MATERIAL DOS` | `16.5` | `11` | `1.500000` | `82.5000` | `5.0000` |
| `PLAFONES` | `MATERIAL UNO` | `27` | `11` | `2.454545` | `285.0000` | `10.5556` |

Total de importes `773.7000`. Venta: `MUROS` `10 × 158.93 + 4 × 200 = 2389.3000`; `PLAFONES` `11 × 158.93 = 1748.2300`. Sugerido: `MUROS` `10 × 133.175 + 4 × 174.245 = 2028.7300`; `PLAFONES` `11 × 133.175 = 1464.9250`. El orden de los renglones sigue `(str(tipo_partida_id), clave)`: las constantes `MUROS` y `PLAFONES` de `soporte_tkt016.py` se eligen para que `str(MUROS) < str(PLAFONES)` (`00000000-0000-0000-0000-000000000001` y `…0002`).

### `CA-10` con la opción recomendada de `P-1`

- La fixture `oraculo_explosion_union` reutiliza `_bytes_catalogo_real("CIMENTA_EXPLOSION_UNION", "la explosión AP-058-25")` y decodifica UTF-8.
- El archivo es un CSV con encabezado `clave,cantidad,importe`, punto decimal y sin separador de miles, extraído una vez a mano del libro `AP-058-25 EXPLOSION DE INSUMOS` y guardado fuera del repositorio junto a él. Se lee con `csv.DictReader`; la clave se normaliza con `normalizar_clave_insumo` y las cifras se construyen con `Cantidad(texto)` y `Dinero(texto)`.
- La prueba lee `archivo_union` con `leer_libro_presupuesto_bytes`. Si `libro.asociaciones == ()`, hace `pytest.skip` con el motivo «PA-16.6 · PA-T3: el libro de análisis de Union no asocia ningún concepto».
- Asigna un solo UUID a todos los conceptos, porque el oráculo no distingue tipo de partida, y llama a `calcular_explosion`. Exige un `ExplosionCalculada`; un rechazo hace fallar la prueba mostrando sus causas.
- Compara tras `cuantizar()`: el número de renglones contra el de filas del CSV, la cantidad presupuestada de cada clave contra la del CSV cuantizada a 4, y `sumar` de los importes contra la suma del CSV cuantizada a 4 (`2755187.2112` según el PRD).

### Mutación

Ruta crítica de dinero: la hace `tester-backend` en A8, uno por uno, revirtiendo cada mutante. Se documenta en `impl.md` qué se mutó y qué test cayó.

| # | Mutante | Test que debe ponerse rojo |
|---|---|---|
| M-1 | Sugerido `pu − utilidad − indirectos` → `pu − utilidad + indirectos` | TC-09 |
| M-2 | Rendimiento como promedio simple de los rendimientos | TC-06 |
| M-3 | Costo como promedio simple de los costos | TC-06 |
| M-4 | Quitar el filtro `TipoInsumo.MATERIAL` de la agregación y de las causas | TC-07 |
| M-5 | Cantidad `<= 0` → `< 0` | TC-13 |
| M-6 | Rendimiento `<= 0` → `< 0` | TC-16 |
| M-7 | Sugerido `< 0` → `<= 0` | TC-19 |
| M-8 | Cuantizar cada producto `q × r` antes de sumarlo | TC-11 |
| M-9 | `_MODO_REDONDEO = ROUND_HALF_EVEN` en `tipos_base` | TC-11 |
| M-10 | Devolver el rechazo con la primera causa encontrada | TC-13 |
| M-11 | Precio unitario del catálogo en lugar del pie del análisis | TC-09 |
| M-12 | Sumar `q` en `cantidad_conceptos` por cada renglón de insumo, no por concepto | TC-08 |
| M-13 | Cargo ausente tomado como cero | TC-15 |
| M-14 | Agrupar solo por clave, sin tipo de partida | TC-05 y TC-25 |
| M-15 | Saltarse el paso 3 cuando ya hay otras causas | TC-20 |

## Impacto

Análisis del arquitecto, para que `revisor-impacto` lo contraste en el gate.

| Qué se toca | Quién depende | Riesgo | Mitigación |
|---|---|---|---|
| `tipos_base/numericos.py`: `_cociente` partido en `_dividir` más envoltura | Todo uso de `Cantidad / Cantidad` y `Dinero / Dinero` | Cambiar sin querer el resultado o el mensaje de la división existente | TC-29 a TC-33b de TKT-004 siguen en verde sin tocarse (A1, TC-23); M-9 confirma que el modo sigue centralizado |
| `tipos_base/__init__.py`: dos nombres más | Los diez módulos | Ninguno: solo añade | `lint-imports` (contrato `tipos-base-puro`) |
| `presupuesto/dominio/explosion.py` (nuevo) | TKT-017 (caso de uso de congelado y ruta de la explosión), TKT-020 (`RN-03` por volumen) | Que TKT-017 persista sin cuantizar | `serializar()` rechaza un valor sin cuantizar; el docstring de `calcular_explosion` dice que la salida es `cuantizar()`; se anota en `delta.md` |
| `herramientas/soporte_tkt016.py`, `tests/conftest.py` | Pruebas | `verificar_float` solo recorre `tipos_base/**` y `cimenta/*/dominio/**` (`herramientas/verificar_float.py:23`): el soporte queda sin vigilancia de `float` en firmas, igual que `soporte_tkt013.py` y `soporte_tkt014.py` | Los importes del soporte se construyen desde cadena; la revisión lo comprueba |
| `_dividir` (refactor de `_cociente`) | Mensaje de `ZeroDivisionError`, que hoy usa `type(a).__name__` y `type(b).__name__` (`numericos.py:289-292`) | Perder los nombres de tipo o la subcadena «regla 12» | `_dividir` recibe los dos operandos, no solo sus `Decimal`; TC-03 y `test_tkt004_ca04_division_entre_cero` lo exigen |
| `docs/` | Lectores | Desincronizar `PA-23` entre PRD, arquitectura, `CLAUDE.md` y ADR-020 | La fila A7 los cambia juntos (ver `P-6`) |

**Fronteras entre módulos:** No. Todo queda dentro de `presupuesto/dominio/` y `tipos_base`.

## Documentación afectada

| Documento | Qué cambia | Fila |
|---|---|---|
| `docs/02-arquitectura.md` §7.4 | La lista «Solo existen…» añade `cociente_rendimiento` (`Cantidad`, `Cantidad` → `Rendimiento`) y `cociente_precio_unitario` (`Dinero`, `Cantidad` → `Dinero`), con 28 dígitos y `ZeroDivisionError`, y aclara que son funciones y no operadores. `ROUND_HALF_UP` deja de ir `(asumido)`: lo confirmó la persona dueña el 2026-11-03 | A7 |
| `docs/01-descripcion-producto.md` | `PA-23` sale de «Preguntas abiertas» (fila de la línea 554) y entra en la tabla de respondidas con «`ROUND_HALF_UP`, confirmado por la persona dueña el 2026-11-03». El conteo «**Cuatro.**» de la línea 545 pasa a «**Tres.**» y se quita la mención de `PA-23` de la frase que lo acompaña | A7 |
| `README.md` (líneas 39 y 257) y `llms.txt` (línea 16) | El conteo de preguntas abiertas pasa de cuatro a tres sin `PA-23`, y el de resueltas de 19 a 20 | A7 |
| `docs/05-tickets-trabajo.md`, ficha de TKT-016 (líneas 703 a 720) | Si se aprueba `P-3`, nota «Partición en dos tickets hermanos» con su tabla, como la de TKT-014 (líneas 669 a 675), y revisión de la dependencia de TKT-017 (línea 726). En cualquier caso, nota en el criterio de los 27 insumos y $2,755,187.21: se ejecuta tras variables de entorno y hoy queda omitido por `PA-T3` (`PA-16.6`) | A7 (partición) y B3 (nota del criterio) |
| `backend/tests/test_tipos_base_redondeo.py` (línea 4) | El comentario deja de decir `ROUND_HALF_UP (asumido, …)` y cita `PA-23` cerrada. Este archivo sale de la lista de `git diff` vacío de TC-23 (`P-7`) | A1 |
| `docs/03-modelo-datos.md` | La tabla «Dos tablas…» (líneas ~300 a 303): el sugerido es `Σ cantidad × (P.U. − utilidad − indirectos)` del análisis, sin restar IVA; el volumen añade que el rendimiento congelado y el costo unitario son promedios ponderados por cantidad. Sin tocar el diagrama Mermaid | A7 |
| `docs/adr/20261103-explosion-por-tipo-de-partida.md` (ADR-036, si se aprueba `P-4`) | MADR: promedio ponderado frente a detalle por concepto, P.U. del análisis frente al del catálogo, sugerido desde los cargos del análisis, rechazo todo o nada. Con la fila en `docs/adr/README.md` y los conteos de ADR en `README.md`, `llms.txt` y `CLAUDE.md` que exige `tools/tests` | A7 |
| `docs/adr/20261019-tipos-numericos-base.md` (ADR-020) | La línea 32 («Elegida, como supuesto (asumido)…») pasa a decir que `PA-23` confirmó `ROUND_HALF_UP` el 2026-11-03; la condición de revisión de la línea 78 se ajusta; nota de los dos cocientes añadidos | A7 |
| `backend/tipos_base/numericos.py` (comentario de `_MODO_REDONDEO`, línea 28, y docstring de `cuantizar`, línea 185) | Quitan `(asumido, PA-T5)` y citan `PA-23` cerrada | A1 |
| `frontend/src/compartido/dinero/dinero.ts` (línea 3) | Sin cambio: cita `PA-T5` pero no dice `(asumido)`, y el frontend queda fuera de las capas del ticket. Se anota en `delta.md` como residuo aceptado (`P-7`) | — |
| `CLAUDE.md`, regla 1, y `.claude/skills/conv-dominio-python/SKILL.md` | Quitan `(asumido)` de `ROUND_HALF_UP`. **Cambiar `CLAUDE.md` exige la aprobación explícita de la persona dueña (`P-6`)** | A7 |
| `docs/arranque-local.md`, sección de catálogos reales | Añade `CIMENTA_EXPLOSION_UNION`, el formato del oráculo según `P-1`, la prueba `tests/test_tkt016_archivo_real.py` y que hoy se omite por `PA-T3` | B3 |

`docs/api/openapi.yaml` no cambia: sus hallazgos son de TKT-017 (`PA-16.7`). `test_tkt010_semilla_local.py` tampoco. Las listas de ADR de `docs/02-arquitectura.md` (líneas 644 a 646) y de `docs/06-stack-tecnologico.md` (624 a 626) llegan solo hasta el ADR-023 y no reciben el 036.

## ¿Merece ADR?

**Sí, recomendado (`P-4`).** Quien llegue y vea `rendimiento_congelado` en `explosion_presupuesto` se preguntará si es el del análisis o un promedio, y por qué el sugerido no sale del precio del catálogo. Hubo opciones descartadas reales, decididas por la persona dueña el 2026-11-03: detalle por concepto frente a promedio ponderado (cambiaba el esquema y la unicidad), precio del catálogo frente al del análisis (Union trae `#REF!` en el catálogo), y cargos ausentes tomados como cero frente a rechazo. Hoy viven solo en `_index.md` y `spec.md`, que son artefactos de ticket. La elección de funciones con nombre en lugar de operadores en `tipos_base` es menor y entra como consecuencia en el mismo ADR, no en uno propio.

Coste: el ADR mueve el conteo de decisiones (35 → 36) en `CLAUDE.md`, `README.md` y `llms.txt`, como hizo TKT-014 en su fila B4.

## Experimentos

| # | Qué mide | Cómo | Resultado esperado | Si no coincide |
|---|---|---|---|---|
| E-1 | Que las herramientas pasan antes del cambio. Hoy es una afirmación **(sin ejecutar)**: `ruff`, `mypy`, `lint-imports` (quince contratos, incluidos `dominio-sin-framework` y `tipos-base-puro`), `verificar_float` y las suites de TKT-004, TKT-013 y TKT-014 | Fila A0 | Todo en verde | `/sdd-escalar` antes de A1: el fallo es previo al ticket |
| E-2 | Que el lector deja `precio_unitario` del pie aunque marque `PU_NO_CUADRA` en el libro de `CA-8` **(sin ejecutar; leído en `lectura_analisis.py`, líneas 636 a 667)** | La primera ejecución de TC-24 en B1 | `APU-B` con `Dinero("200")` y `APU-C` con `Dinero("158.93")` | El tester ajusta los cargos o el pie del libro para que cuadre, y anota el ajuste en `impl.md`; la regla no cambia |
| E-3 | Que el libro real de Union sigue sin asociaciones (medido en TKT-014, TC-44: `lu.asociaciones == ()`) | B2, con las variables definidas | TC-26 `SKIPPED` por `PA-T3` | Si ya asocia, TC-26 corre de verdad; si falla, es un hallazgo de reconciliación que se escala, no se ajusta el test |

## Pasada adversarial

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | `CA-2` pide que el rendimiento por la suma reproduzca la cantidad «sin diferencia», y a seis decimales es falso (`1.083333 × 300 = 324.9999`) | El resultado conserva precisión completa y la identidad se comprueba antes de cuantizar, en la escala de la columna. Escrito en «Cómo se lee la última línea de `CA-2`» y en TC-06 |
| 2 | Alta | `importe = cantidad_presupuestada × costo_unitario` con el costo ya dividido no da `27100.00` exacto | El importe es `Σ(q × r × c)`, equivalente en aritmética exacta y sin división. TC-06 lo fija |
| 3 | Alta | El oráculo `AP-058-25` no tiene lector ni disposición medida: escribir uno sería inventar | `P-1` a la persona dueña, con la opción mínima recomendada. B2 no se ejecuta sin respuesta |
| 4 | Media | Con datos inválidos en un tipo, su sugerido no está definido, y comprobar su signo daría causas espurias | El paso 3 solo evalúa los tipos con todos sus datos de importe completos, y se ejecuta aunque haya otras causas. TC-20 y M-15 |
| 5 | Media | Un análisis puede listar la misma clave en dos renglones; sumar su concepto dos veces en `Σ q` falsea el rendimiento | `cantidad_conceptos` cuenta cada concepto una vez, como dice `M1` («de los conceptos que usan ese insumo»). TC-08 y M-12 |
| 6 | Media | Dos renglones del mismo tipo de cargo (dos `UTILIDAD`) no tienen comportamiento definido | `P-2`. El diseño suma los dos, a reserva de lo que decida la persona dueña |
| 7 | Baja | Un insumo `MATERIAL` sin unidad no cuenta en el conflicto de unidades y pasa | Igual que `proponer_insumos` de TKT-014b; TKT-015 lo reporta como hallazgo de importación. `P-5` |
| 8 | Baja | Un valor que no cabe en su columna hace que `cuantizar()` lance `ValueError`, que no es una causa de rechazo | Es un error de programa de `tipos_base`, no una regla de la spec; con importes reales de obra no ocurre. Queda en riesgos |
| 9 | Baja | Usar `uuid.UUID` en el dominio ata la entrada al tipo de la columna | Es biblioteca estándar sin E/S, y `tipo_partida_id` es `uuid` en el esquema. La regla no lo interpreta: solo agrupa y ordena por `str`. `revisor-impacto` confirmó que el contrato `lista_blanca` lo admite y que `auditoria` e `identidad` ya importan `uuid` en su dominio |
| 10 | Media | La partición propuesta no lleva ninguna parte bajo las ~400 líneas: TKT-016a ronda las 815 (300 de producción y el resto pruebas y documentación), y TKT-016b no tiene código de producción | Se presenta a la persona dueña en `P-3` con las cifras: partir reduce el PR de la regla, pero no cumple el umbral; no partir deja un PR de ~1,080 líneas con solo ~300 de producción |
| 11 | Media | `revisor-impacto`: cerrar `PA-23` desincroniza conteos en `README.md` y `llms.txt`, comentarios `(asumido)` en ADR-020, `numericos.py` y una prueba de TKT-004, y la ficha de TKT-016 en `docs/05` | Añadidos a «Documentación afectada» con su línea y su fila. El choque de TC-23 con `test_tipos_base_redondeo.py` y el residuo de `dinero.ts` van a `P-7` |

## Riesgos

| Riesgo | Probabilidad | Impacto | Qué se hace |
|---|---|---|---|
| `CA-10` queda omitido siempre porque Union no asocia análisis (`PA-T3`) | Alta | Medio: la cifra de $2,755,187.21 no se reconcilia en este ticket | Aceptado en `PA-16.6`. El motivo del `skip` lo dice, y `delta.md` lo hereda a quien resuelva `PA-T3` |
| Las claves del oráculo no coinciden con las descripciones normalizadas de los análisis | Media | Medio: la reconciliación fallaría sin defecto en la regla | El oráculo se normaliza con `normalizar_clave_insumo`. Si aun así no coinciden, se escala como hallazgo de datos |
| TKT-017 persiste el resultado sin `cuantizar()` | Baja | Medio: PostgreSQL redondearía por su cuenta | `serializar()` lo rechaza; el docstring y `delta.md` lo dicen |
| La partición se rechaza y el ticket pasa de ~1,000 líneas en un solo PR | Media | Bajo: más revisión, el mismo orden | Las filas no cambian; se ejecutan seguidas |
| Un valor fuera de escala hace lanzar `ValueError` a `cuantizar()` | Muy baja | Bajo | Error de programa visible; no se convierte en causa sin una decisión |

## Preguntas para el gate

Cada una con la recomendación. Ninguna reabre una decisión de la spec.

| # | Pregunta | Opciones | Recomendación |
|---|---|---|---|
| P-1 | ¿Cómo se lee el oráculo `AP-058-25 EXPLOSION DE INSUMOS` en `CA-10`? Nadie ha medido su disposición, no está en el repositorio y el README dice que son dos archivos | **A.** `CIMENTA_EXPLOSION_UNION` apunta a un CSV `clave,cantidad,importe` extraído a mano una vez del libro y guardado junto a él, fuera del repositorio; se lee con `csv` en ~15 líneas. **B.** La variable apunta al `.xlsx`, se mide su disposición en un experimento con el archivo y se escribe un lector de prueba; es un lector nuevo que la spec no previó. **C.** Comparar solo los literales documentados (27 insumos y `2755187.2112`) sin leer el archivo; pierde «la cantidad de cada uno» y cambia `CA-10` | **A.** Es la más pequeña, no inventa ninguna disposición y hoy la prueba se omite igual por `PA-T3`. Si se elige B, B2 se rediseña con su experimento antes de ejecutarse |
| P-2 | Si un análisis trae dos renglones de `UTILIDAD` (o de `INDIRECTOS`), ¿se restan los dos o se rechaza? | Sumar los dos y restar el total · rechazar como dato ambiguo | **Sumar.** «Quitar la utilidad» es quitar todos sus renglones; en los libros reales medidos hay uno de cada uno |
| P-3 | ¿Se parte el ticket en TKT-016a (la regla) y TKT-016b (`CA-8` y `CA-10`)? | Partir · un solo ticket | **Partir.** La parte a cierra `M1` a `M4` con todos sus rechazos; la b es solo evidencia |
| P-4 | ¿Se escribe ADR-036 con las decisiones del 2026-11-03? | Sí · no, quedan en la spec | **Sí**, por las opciones descartadas que cambian la semántica de una columna congelada |
| P-5 | ¿Un insumo `MATERIAL` sin unidad se ignora en el conflicto de unidades? | Ignorarlo, como TKT-014b · rechazarlo con una causa nueva | **Ignorarlo.** Una causa nueva sería una regla que `M4` no lista |
| P-7 | Al cerrar `PA-23`, ¿se edita el comentario `(asumido)` de `tests/test_tipos_base_redondeo.py` (TKT-004), sacándolo de la regresión de TC-23, y se deja `frontend/src/compartido/dinero/dinero.ts` como residuo anotado? | Editar la prueba y dejar el frontend · no tocar ninguna prueba de TKT-004 y anotar los dos residuos | **Editar la prueba y dejar el frontend**: es un comentario, no una aserción, y el frontend está fuera de las capas del ticket |
| P-6 | Al cerrar `PA-23`, ¿se quita `(asumido)` de `ROUND_HALF_UP` en `CLAUDE.md` (regla 1) y en `conv-dominio-python`? | Sí, en A7 · dejarlo para otro cambio | **Sí, en A7**, para que el PRD, la arquitectura y las instrucciones no se contradigan |
