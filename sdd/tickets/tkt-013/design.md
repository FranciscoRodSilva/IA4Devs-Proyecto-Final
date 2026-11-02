# Design · TKT-013 · Lector del catálogo de conceptos

> [← index](_index.md) | [← spec](spec.md) | Siguiente: [impl →](impl.md)

## Estrategia

El lector se parte en dos capas del módulo `presupuesto`. **Todo lo que decide vive en `dominio/`**: la elección de la hoja, la localización del encabezado y de las columnas, la clasificación de cada fila, la reconstrucción de la jerarquía por posición, la normalización de la unidad, la interpretación de cada número y los hallazgos. El dominio recibe filas ya extraídas como tuplas de valores (`str`, `int`, `Decimal` o `None`) y devuelve un valor en memoria, sin E/S. **`infraestructura/` solo abre el libro con openpyxl** (`read_only=True`, `data_only=True`), entrega al dominio los nombres de las hojas y las filas de la hoja elegida, y convierte en esa frontera cada `float` de openpyxl en `Decimal` por su representación más corta. Así el dominio se prueba entero sin openpyxl, `verificar_float` no ve ningún `float` en firmas de `dominio/`, y openpyxl queda encerrado en un archivo de unas sesenta líneas.

El lector recibe **bytes**: el análisis correrá en un `ProcessPoolExecutor` (TKT-015) y los bytes viajan al proceso trabajador sin archivo temporal. El resultado es un `CatalogoLeido` inmutable. No hay puerto, porque el dominio no llama a la infraestructura, ni se publica en `cimenta.presupuesto.interfaz`, porque sus consumidores (TKT-015 y TKT-018) son del mismo módulo.

La profundidad (`PA-T2`) se resuelve con una regla determinista de **corridas de filas sin código**: hay cuatro niveles de agrupación (raíz, nivel, área y partida); **la primera corrida de la hoja se alinea a la raíz y cada corrida posterior se alinea a la partida**. Es la única lectura que cuadra con las dos estructuras reales, y su límite conocido queda cubierto por una prueba de oráculo sobre los archivos completos (ver «La regla de profundidad»).

El orden suma unas **1,455 líneas** (unas 470 de producción, unas 935 de pruebas y unas 50 de documentación), más del triple del tope de unas 400 por cambio: es la **condición de parada 3**. Se recomienda partir el ticket en dos tickets hermanos con un PR cada uno, como TKT-011: **TKT-013a** (dominio puro, sin dependencia nueva) y **TKT-013b** (openpyxl, lector de infraestructura, archivos reales y el Should S1). Este diseño cubre los dos y numera sus filas `A` y `B`.

## Partición propuesta (condición de parada 3)

| Ticket | Musts | Contenido | Líneas estimadas | Depende de | Filas |
|---|---|---|---|---|---|
| TKT-013a | `M1`, `M2`, `M3` y `M5` sobre filas en memoria; `M4` en su parte (el valor en memoria y los tipos) | `dominio/catalogo.py` y `dominio/lectura_catalogo.py`, sus pruebas puras y el criterio de la ficha de `docs/05` | ~735 (≈ 300 de producción, ≈ 425 de pruebas, ≈ 10 de documentación) | TKT-011b (archivado) | A0 a A4 |
| TKT-013b | `M1` a `M5` contra el libro real; `M4` (la conversión de `float`); `M6`; `S1` | `openpyxl` y `types-openpyxl` en `pyproject.toml` y `uv.lock`, `infraestructura/lector_catalogo.py`, `dominio/totales_catalogo.py`, la sección TKT-013 de `conftest.py`, las pruebas sintéticas y las de los archivos reales, la documentación | ~720 (≈ 95 de producción: B1 y B2; ≈ 585 de pruebas, incluida la sección de `conftest.py` con `LibroCatalogo`; ≈ 40 de documentación) | TKT-013a | B0 a B5 |

En la ficha de `docs/05` la tabla usa las columnas del precedente de TKT-011 y TKT-010 (`Ticket | Contenido | Migración | Depende de | Filas del diseño`), con «Ninguna» en la migración de los dos.

**El orden de fusión es fijo: a → b.** TKT-013 queda como paraguas, conserva la spec y este diseño, y se cierra cuando se cierran los dos. TKT-014 depende de TKT-013b.

**Por qué esta frontera.** TKT-013a no añade dependencia ni toca archivos externos: sus pruebas alimentan al dominio con tuplas. TKT-013b es el único que trae openpyxl, `pip-audit` y los archivos reales. El Should `S1` va en b para que, si hay que recortar, se recorte sin reabrir a.

**Alternativa descartada:** partir en tres (dominio de jerarquía, lector openpyxl, `S1`). `S1` son unas 100 líneas: un PR de ese tamaño cuesta más en ceremonia que lo que ahorra en revisión.

### Criterios de la spec que hay que ajustar si se aprueba la partición

| Criterio | Dice hoy | Debe decir |
|---|---|---|
| `CA-1`, `CA-2`, `CA-5`, `CA-7`, `CA-12` | Contra los archivos reales | Solo TKT-013b. TKT-013a cubre la misma lógica con filas en memoria |
| `CA-3`, `CA-4`, `CA-9`, `CA-11` | Contra los archivos reales | TKT-013a con filas en memoria que repiten el patrón de corridas de los archivos (sin nombres del cliente); TKT-013b contra los reales |
| `CA-6`, `CA-8`, `CA-10` | Hoja sintética | TKT-013a con filas en memoria; TKT-013b con un libro construido con openpyxl |
| `CA-13` | Totales | Solo TKT-013b |
| `CA-R3` | `pip-audit` | Solo TKT-013b |
| Definition of Done | «Contra los dos archivos reales» | TKT-013b. TKT-013a no lee ningún archivo |

## Escalera de decisión

| Objeto | Peldaño donde paró | Por qué |
|---|---|---|
| Dependencia `openpyxl` | 3 · reuso de una decisión registrada | La elige el stack ([`06-stack-tecnologico.md`](../../../docs/06-stack-tecnologico.md) §4.5); el ticket solo la incorpora. No es nativo de Python: la biblioteca estándar no lee `.xlsx` |
| Dependencia de desarrollo `types-openpyxl` | 5 · objeto nuevo, lo más pequeño posible | `uv run mypy .` corre sobre todo `backend/`: sin los tipos, `import openpyxl` falla con `import-untyped` `(sin ejecutar, E-9)` |
| `dominio/catalogo.py`: `NodoLeido`, `Ruta`, `ConceptoLeido`, `Hallazgo`, `CatalogoLeido`, `Profundidad`, `CausaHallazgo` | 5 · objeto nuevo | `M4` exige un valor en memoria y `M5` un hallazgo con hoja, fila, columna y valor original. `importacion_error` no sirve: es una tabla, y `PA-T10` y `PA-T11` excluyen persistir y usar su `tipo` |
| Cantidad, precio unitario e importe como `Cantidad` y `Dinero` | 3 · reuso de `tipos_base` | `Cantidad` es `NUMERIC(14,4)` y `Dinero` `NUMERIC(18,4)`; los dos conservan la precisión completa hasta `cuantizar()`, que es lo que pide `PA-T9`. `Cantidad × Dinero` ya devuelve `Dinero` exacto para `S1` |
| `UNIDADES_ADMITIDAS` | 5 · objeto nuevo, con prueba de sincronía | Las ocho unidades solo existen hoy en el `CHECK` de la migración `0006` (invariante 27). El dominio no puede leer la base, así que se copia la constante y una prueba la compara con `pg_get_constraintdef('ck_concepto_unidad')` |
| `ERRORES_DE_FORMULA` | 5 · objeto nuevo, con prueba de sincronía | Los siete literales de error de Excel. El dominio no puede importar `openpyxl.cell.cell.ERROR_CODES`; una prueba de infraestructura los compara |
| `dominio/lectura_catalogo.py`: `elegir_hoja`, `analizar_hoja`, `catalogo_sin_conceptos`, `normalizar_unidad`, `interpretar_numero`, `letra_de_columna` | 5 · objeto nuevo | No existe ningún lector. Son funciones puras: cada una se prueba sin openpyxl ni base |
| Columnas localizadas (`_Columnas`, privada) | 5 · objeto nuevo, privado | Seis índices que viajan juntos de la localización a la lectura de filas. No se publica |
| `infraestructura/lector_catalogo.py`: `leer_catalogo` | 5 · objeto nuevo | El único sitio que importa openpyxl. Abre, entrega filas, cierra |
| Conversión de `float` a `Decimal` | 2 · nativo de Python | `repr(float)` da la representación decimal más corta que vuelve al mismo `float`, y `Decimal(str)` la toma exacta. No hace falta biblioteca ni contexto decimal |
| Puerto del lector en `dominio/` | 1 · YAGNI, fuera | El dominio no llama a la infraestructura: no hay inversión que hacer |
| Exportar el lector en `cimenta.presupuesto.interfaz` | 1 · YAGNI, fuera | Ningún otro módulo lo usa; TKT-015 y TKT-018 son de `presupuesto` |
| Caso de uso en `aplicacion/` | 1 · YAGNI, fuera | No hay transacción ni orquestación: lo crea TKT-018 con la importación |
| `dominio/totales_catalogo.py`: `TotalesCatalogo`, `totalizar`, `importe_calculado` | 5 · objeto nuevo | Lo exige el Should `S1` (`CA-13`). Recortable sin tocar el resto |
| Sección «TKT-013» de `conftest.py`: `LibroCatalogo` y las fixtures `libro_catalogo`, `archivo_eniti` y `archivo_union` | 5 · objeto nuevo, código de prueba | `PA-T3`: el libro sintético se construye en `tmp_path` con openpyxl y los reales llegan por variable de entorno con `skip` visible. Va en `conftest.py`, como `DatosPresupuesto`, para que mypy lo resuelva sin tocar su configuración |
| Progreso y latido durante la lectura | 1 · YAGNI, fuera | Son de TKT-015 |
| Clasificación en los tipos de `importacion_error` | 1 · YAGNI, fuera | Won't (`PA-T10`); es de TKT-015 |
| `defusedxml` | Pregunta P10 | openpyxl no se protege por omisión de la expansión de entidades XML y recomienda instalar `defusedxml` (documentación consultada con Context7). Es endurecimiento de la dependencia que este ticket añade, pero ningún Must lo pide |

Ningún objeto paró en el peldaño 4 tocando un invariante registrado: la escalera no se rompe.

## La regla de profundidad (`PA-T2`)

Las filas de nivel, área y partida tienen la misma forma: código vacío y nombre en la columna de la descripción. Lo único que las distingue es su posición. El lector reconoce **cuatro niveles de agrupación**, en este orden: `RAIZ`, `NIVEL`, `AREA` y `PARTIDA` `(asumido, P3)`. La raíz es la fila de título que ENITI trae en la fila 9 (`ACABADOS EN MUROS Y PLAFONES`) y que encabeza la ruta de `CA-3`; no tiene tabla en el modelo.

**Corrida** es la sucesión de filas de grupo entre dos filas de concepto (o entre el encabezado y el primer concepto). Las filas vacías y las filas sin código ni nombre no cortan una corrida: se saltan. Cuando aparece un concepto, la corrida pendiente se aplica así:

1. Si la corrida tiene más de cuatro filas, las primeras sobrantes no se colocan: cada una da un hallazgo `PROFUNDIDAD_EXCEDIDA` y se aplican las cuatro últimas.
2. **La primera corrida de la hoja se alinea a la raíz**: sus filas ocupan `RAIZ`, `NIVEL`, `AREA` y `PARTIDA` en ese orden, hasta donde alcancen; las posiciones que sobran quedan vacías.
3. **Toda corrida posterior se alinea a la partida**: una corrida de longitud *k* reemplaza los *k* niveles más profundos y conserva los de arriba.
4. Al reemplazar un nivel, los más profundos que la corrida no cubre quedan vacíos. Con la regla 3 eso no ocurre nunca; con la regla 2, sí.
5. Una corrida al final de la hoja, sin concepto después, se descarta sin hallazgo `(asumido, P5)`.
6. El concepto toma la ruta vigente. Si su partida está vacía, da un hallazgo `CONCEPTO_SIN_PARTIDA` y conserva la ruta parcial (`PA-T13`).

Cómo resuelve los casos de la spec:

| Filas | Corrida | Regla | Resultado |
|---|---|---|---|
| ENITI 9 a 12 | 4 filas, primera de la hoja | 2 | raíz `ACABADOS…`, nivel `NIVEL 1`, área `LOBBY Y PASILLO`, partida `MUROS` → `CA-3` |
| ENITI 15 | 1 fila | 3 | Nueva partida en la misma área |
| ENITI 27 y 28 | 2 filas | 3 | Nueva área `CUBO DE ESCALERAS` y partida `ENCHAPES` → `CA-3` |
| Union 9 a 11 | 3 filas, primera de la hoja | 2 | raíz, nivel `Nivel 1`, área `Pasillos`, **sin partida** → los conceptos 12 a 16 dan `CONCEPTO_SIN_PARTIDA` → `CA-9` |
| Union 17 y 18 | 2 filas | 3 | Nueva área `DPTO. 111 TIPO  3R` y partida `Muros` → `CA-4` |

La alineación a la partida en la primera corrida (la descartada) leería Union 9 a 11 como nivel, área `Nivel 1` y partida `Pasillos`, y armaría mal toda la obra sin un solo hallazgo. La alineación a la raíz en todas las corridas leería ENITI 15 como una raíz nueva.

**Límite conocido.** Un catálogo sin fila de título, cuyas tres primeras filas de grupo serían nivel, área y partida, se leería con la ruta corrida un nivel a la derecha. Además, un área sin partida que no sea la primera de la hoja, o un área sin ningún concepto seguida de otra, se leería corrida a la derecha sin hallazgo. Ninguno de los dos casos se ha visto en los archivos reales `(sin ejecutar, E-8)`. Lo cubre la prueba de oráculo TC-36: sobre los dos archivos completos, todo nodo en posición `NIVEL` se llama `NIVEL n` o `ROOF GARDEN` (sin distinguir mayúsculas) y todo nodo en posición `PARTIDA` pertenece al vocabulario de partidas que mida E-8. El lector no usa nombres (`CA-4`); la prueba sí, porque es el oráculo, no la regla. Si E-8 encuentra uno de esos casos, la fila A0 se detiene y se escala.

## Capas afectadas

### Dominio

| Archivo | Qué | Regla |
|---|---|---|
| `backend/cimenta/presupuesto/dominio/catalogo.py` | Objetos de valor y constantes (detalle abajo) | HDU-001 esc. 5, 6, 8 y 27; invariante 27; regla 1 de `CLAUDE.md` |
| `backend/cimenta/presupuesto/dominio/lectura_catalogo.py` | Localización, clasificación, jerarquía, unidad, números y hallazgos | HDU-001 esc. 5, 6, 8 y 27; `PA-T2`, `PA-T5`, `PA-T6`, `PA-T12`, `PA-T13` |
| `backend/cimenta/presupuesto/dominio/totales_catalogo.py` | `S1`: totales de la previsualización (TKT-013b) | HDU-001 esc. 5 |

Todos con `from __future__ import annotations`, solo biblioteca estándar (`dataclasses`, `decimal`, `enum`, `unicodedata`, `collections.abc`) y `tipos_base`. Ninguno lleva una `RN-xx`: el docstring cita el escenario de HDU-001 y la `PA` que implementa.

#### `catalogo.py`

```python
type ValorCelda = str | int | Decimal | None

UNIDADES_ADMITIDAS: frozenset[str]  # {"M2", "ML", "PZA", "KG", "CAJA", "SACO", "ROLLO", "JORNAL"}
ERRORES_DE_FORMULA: frozenset[str]  # {"#NULL!", "#DIV/0!", "#VALUE!", "#REF!", "#NAME?", "#NUM!", "#N/A"}

class Profundidad(StrEnum):  # RAIZ, NIVEL, AREA, PARTIDA, en ese orden

class CausaHallazgo(StrEnum):
    HOJA_NO_LOCALIZADA       # ninguna hoja empieza por «catalogo»
    HOJA_AMBIGUA             # más de una; detalle con los nombres
    ENCABEZADO_NO_LOCALIZADO # ninguna fila con «código» en la columna A
    COLUMNA_NO_LOCALIZADA    # falta un rótulo o aparece más de una vez; detalle dice cuál
    NINGUN_CONCEPTO          # encabezado sin ninguna fila de concepto debajo
    ERROR_DE_FORMULA         # la celda trae un literal de ERRORES_DE_FORMULA
    NO_ES_NUMERO             # texto u otro valor en una columna numérica, o número fuera de tipos_base
    VALOR_AUSENTE            # celda vacía en un dato del concepto (P6)
    UNIDAD_NO_RECONOCIDA     # la unidad normalizada no está en UNIDADES_ADMITIDAS
    NOMBRE_ILEGIBLE          # fila de grupo cuyo nombre es un literal de error
    CONCEPTO_SIN_PARTIDA     # la ruta del concepto no tiene partida
    PROFUNDIDAD_EXCEDIDA     # corrida de más de cuatro filas

@dataclass(frozen=True, slots=True)
class NodoLeido:
    fila: int
    profundidad: Profundidad
    nombre: str | None          # None si el nombre es ilegible; el original va en el hallazgo

@dataclass(frozen=True, slots=True)
class Ruta:
    raiz: NodoLeido | None
    nivel: NodoLeido | None
    area: NodoLeido | None
    partida: NodoLeido | None

@dataclass(frozen=True, slots=True)
class ConceptoLeido:
    fila: int
    codigo: str
    descripcion: str | None
    unidad: str | None          # normalizada si se reconoce; si no, el texto original sin tocar
    cantidad: Cantidad | None
    precio_unitario: Dinero | None
    importe: Dinero | None      # el del archivo, sin recalcular
    ruta: Ruta

@dataclass(frozen=True, slots=True)
class Hallazgo:
    causa: CausaHallazgo
    hoja: str | None
    fila: int | None
    columna: str | None         # letra, como "E"
    valor_original: str | None
    detalle: str | None = None

@dataclass(frozen=True, slots=True)
class CatalogoLeido:
    hoja: str | None
    fila_encabezado: int | None
    nodos: tuple[NodoLeido, ...]
    conceptos: tuple[ConceptoLeido, ...]
    hallazgos: tuple[Hallazgo, ...]
```

Los nombres de las causas no repiten los de `importacion_error.tipo` (`REF_ROTA`, `UNIDAD_DESCONOCIDA`, `SIN_CONCEPTOS`) a propósito: son hallazgos crudos que TKT-015 traduce (`PA-T10`), y un nombre igual invitaría a guardarlos sin traducir.

#### `lectura_catalogo.py`

| Firma | Qué hace |
|---|---|
| `elegir_hoja(nombres: Sequence[str]) -> str \| Hallazgo` | Normaliza cada nombre (quita espacios de los extremos, acentos por `unicodedata.normalize("NFKD")` sin marcas combinantes, y `casefold`) y se queda con los que empiezan por `catalogo` (`PA-T5`). Uno: lo devuelve tal como venía. Ninguno: `Hallazgo(HOJA_NO_LOCALIZADA, hoja=None, …, detalle="hojas del libro: " + nombres unidos por ", ")`. Más de uno: `Hallazgo(HOJA_AMBIGUA, hoja=None, …, detalle=<candidatas unidas por ", ">)`; nunca elige |
| `analizar_hoja(hoja: str, filas: Iterable[tuple[int, tuple[ValorCelda, ...]]]) -> CatalogoLeido` | Cada elemento es `(número de fila, valores desde la columna A)`. Consume el iterable una sola vez, en orden. Una tupla más corta que una columna localizada se lee como `None` en esa columna |
| `catalogo_sin_conceptos(hallazgo: Hallazgo, hoja: str \| None = None, fila_encabezado: int \| None = None, nodos: tuple[NodoLeido, ...] = ()) -> CatalogoLeido` | Resultado sin conceptos con un único hallazgo de estructura (`CA-10`) |
| `normalizar_unidad(unidad: str) -> str \| None` | `unidad.strip().upper()`; devuelve el resultado si está en `UNIDADES_ADMITIDAS` y `None` si no (`PA-T12`, invariante 27). No quita espacios interiores ni puntos `(asumido, P9)` |
| `interpretar_numero[N: (Cantidad, Dinero)](valor: ValorCelda, tipo: type[N]) -> N \| CausaHallazgo` | `None` o cadena en blanco → `VALOR_AUSENTE`. Cadena cuyo `strip()` está en `ERRORES_DE_FORMULA` → `ERROR_DE_FORMULA`. Cualquier otra cadena → `NO_ES_NUMERO`. `int` o `Decimal` → `tipo(valor)`; si `tipos_base` lanza `ValueError` (más de 40 decimales o magnitud desde 10⁴¹), `NO_ES_NUMERO`. **Nunca devuelve cero en lugar de un rechazo** |
| `letra_de_columna(indice: int) -> str` | Índice desde cero a letra de Excel: `0 → "A"`, `25 → "Z"`, `26 → "AA"` |

**Pasos de `analizar_hoja`**, en este orden:

1. **Encabezado** (`PA-T5`). La primera fila cuya columna A, si es cadena, normalizada con la misma función que la hoja y sin espacios ni puntos, es igual a `codigo`. Si ninguna lo es: `catalogo_sin_conceptos(Hallazgo(ENCABEZADO_NO_LOCALIZADO, hoja=hoja, fila=None, columna="A", valor_original=None, detalle="ninguna fila tiene «Código» en la columna A"), hoja=hoja)`.
2. **Columnas.** Rótulo normalizado de cada celda de texto del encabezado: sin acentos, `casefold`, sin espacios y sin puntos. `codigo` es la columna A. `descripcion` es la inmediatamente a su derecha, sin mirar su rótulo (`PA-T6`; en ENITI dice `ENCHAPES`). `unidad`, `cantidad`, `pu` (de `P.U.`) e `importe` se buscan por rótulo exacto y deben aparecer **una sola vez** `(asumido, P8)`. Si falta uno, aparece dos veces o coincide con la columna de la descripción: `catalogo_sin_conceptos(Hallazgo(COLUMNA_NO_LOCALIZADA, hoja, fila=<fila del encabezado>, columna=None, valor_original=<rótulo esperado>, detalle="no aparece" | "aparece N veces" | "coincide con la descripción"), hoja, fila_encabezado)`. Las demás columnas (`NOTAS`) se ignoran.
3. **Clasificación de cada fila posterior.** Una celda está vacía si es `None` o una cadena en blanco.
   - Código vacío y nombre vacío: se salta, sin hallazgo y sin cortar la corrida, aunque otras columnas traigan valores `(asumido, P5; PA-T7)`.
   - Código vacío y nombre presente: fila de grupo, se añade a la corrida pendiente. Si el `strip()` del nombre está en `ERRORES_DE_FORMULA`, el nodo lleva `nombre=None` y se emite `Hallazgo(NOMBRE_ILEGIBLE, hoja, fila, columna=<letra de la descripción>, valor_original=<texto tal cual>)`; el nodo **conserva su posición en la corrida** (`CA-11`). Si no, el nombre se conserva tal como viene, sin `strip()` (`CA-3`). Un nombre que no es cadena se pasa a texto con `_como_texto`.
   - Código presente: fila de concepto. Antes de leerla se aplica la corrida pendiente (ver «La regla de profundidad»).
4. **Datos del concepto.**
   - `codigo`: `_como_texto(valor)`. Cadena → `strip()`. `int` → `str(valor)`. `Decimal` entero → sin decimales (`Decimal("620001.0")` → `"620001"`); con decimales → `format(valor, "f")`. Si el texto está en `ERRORES_DE_FORMULA`: hallazgo `ERROR_DE_FORMULA` en la columna A, y el concepto se conserva con ese código.
   - `descripcion`: texto, o `None` con hallazgo `VALOR_AUSENTE` `(asumido, P6)`.
   - `unidad`: vacía → `None` y `VALOR_AUSENTE`. Error de fórmula → el texto y `ERROR_DE_FORMULA`. Si no es cadena, se pasa a texto. Si `normalizar_unidad` la reconoce, queda normalizada; si no, **queda el original sin tocar** y se emite `UNIDAD_NO_RECONOCIDA` con el valor original (`CA-6`).
   - `cantidad` con `interpretar_numero(…, Cantidad)`; `precio_unitario` e `importe` con `interpretar_numero(…, Dinero)`. Si devuelve una causa, el campo queda `None` y se emite el hallazgo con su columna y `valor_original = _texto_original(valor)` (`CA-7`, `CA-8`).
   - Ruta vigente; partida vacía → `CONCEPTO_SIN_PARTIDA` con `columna=None` y `valor_original=None` (`CA-9`).
5. **Cierre.** Sin ningún concepto: `catalogo_sin_conceptos(Hallazgo(NINGUN_CONCEPTO, hoja, fila=<fila del encabezado>, columna=None, valor_original=None), hoja, fila_encabezado, nodos)`. Con conceptos: `CatalogoLeido` con los nodos colocados, los conceptos y los hallazgos **en el orden en que aparecen las filas** y, dentro de una fila, en el orden de las columnas.

`_texto_original(valor: ValorCelda) -> str | None`: `None` → `None`; cadena → tal cual; `int` → `str`; `Decimal` → `format(valor, "f")`.

`nodos` contiene solo los nodos colocados, en orden de fila. Los de las corridas descartadas (regla 5) o sobrantes (regla 1) no entran.

#### `totales_catalogo.py` (TKT-013b, `S1`)

```python
@dataclass(frozen=True, slots=True)
class TotalesCatalogo:
    niveles: int
    areas: int
    partidas: int
    conceptos: int
    importe: Dinero | None      # None = «no calculable», nunca cero

def importe_calculado(concepto: ConceptoLeido) -> Dinero | None:
    """cantidad × precio unitario, exacto y sin cuantizar; None si falta cualquiera de los dos."""

def totalizar(catalogo: CatalogoLeido) -> TotalesCatalogo:
    """HDU-001 esc. 5 · S1. Cuenta los nodos por profundidad y suma importe_calculado con sumar()."""
```

`importe` es `None` si **algún** concepto no tiene importe calculable `(asumido, P7)` o si no hay conceptos. `niveles`, `areas` y `partidas` cuentan los nodos de `catalogo.nodos` con esa profundidad.

### Infraestructura

| Objeto | Tipo | Detalle |
|---|---|---|
| `backend/cimenta/presupuesto/infraestructura/lector_catalogo.py` | adaptador | `leer_catalogo(contenido: bytes) -> CatalogoLeido`. Único archivo del repositorio que importa openpyxl |
| `backend/pyproject.toml` y `backend/uv.lock` | dependencia | `openpyxl` en `dependencies`; `types-openpyxl` en el grupo `dev`. Con `uv add`, que fija la última versión compatible con Python 3.14 |

**Migración:** ninguna (`PA-T11`).

`leer_catalogo` hace exactamente esto:

1. `libro = load_workbook(BytesIO(contenido), read_only=True, data_only=True)`.
2. En un `try` / `finally` que siempre llama a `libro.close()` (en modo de solo lectura el libro se cierra a mano, según la documentación consultada con Context7):
   - `eleccion = elegir_hoja(libro.sheetnames)`. Si es un `Hallazgo`, devuelve `catalogo_sin_conceptos(eleccion)`.
   - `hoja = libro[eleccion]`. Si no es `ReadOnlyWorksheet` (por ejemplo, una hoja de gráfico), devuelve `catalogo_sin_conceptos(Hallazgo(HOJA_NO_LOCALIZADA, hoja=eleccion, fila=None, columna=None, valor_original=None, detalle="no es una hoja de cálculo"))`.
   - `hoja.reset_dimensions()`, para que unas dimensiones mal declaradas en el archivo no corten la lectura (documentación de openpyxl, modo de solo lectura).
   - Devuelve `analizar_hoja(eleccion, ((numero, tuple(_a_valor_celda(v) for v in valores)) for numero, valores in enumerate(hoja.iter_rows(values_only=True), start=1)))`.
3. `_a_valor_celda(valor: object) -> ValorCelda`, en este orden: `None` o `str` → tal cual; `bool` → `"TRUE"` o `"FALSE"` (**antes** que `int`, porque `bool` es subclase de `int` y `Cantidad(True)` lanza `TypeError`); `int` → tal cual; `float` → `Decimal(repr(valor))` (`PA-T9`, ver abajo); cualquier otro (`datetime`, `time`, `timedelta`) → `str(valor)`, que en una columna numérica da `NO_ES_NUMERO`.

**Variante B, decidida de antemano.** Si E-3 muestra que `iter_rows` en modo de solo lectura **no** entrega las filas vacías intermedias (y entonces `enumerate` numeraría mal), el paso 2 itera con `values_only=False` y toma el número de fila de la primera celda que no sea `EmptyCell` (`cell.row`), saltando las filas sin ninguna. Quien ejecuta no elige: aplica B si y solo si E-3 falla, y lo anota en `impl.md`.

**La conversión del número (`PA-T9`).** openpyxl entrega `int` o `float` `(sin ejecutar, E-2)`. `Decimal(repr(f))` toma la cadena más corta que vuelve exactamente al mismo `float`: `16.089` queda `Decimal("16.089")`, y un `16.089000000000002` guardado así en el archivo queda tal cual. Es determinista (`CA-12`), no redondea y deja `cuantizar()` para la materialización (TKT-017). `repr` puede dar notación científica (`1e-05`); `Decimal("1e-05")` la acepta, y `Cantidad` y `Dinero` la reciben como `Decimal`, no como cadena, así que su expresión regular de decimal llano no interviene. Tiene como mucho 17 dígitos significativos, así que la heurística `_viene_de_float` de `tipos_base` (más de 18) no lo rechaza. Se descarta `Decimal(f)` (arrastra los 50 dígitos del binario y `tipos_base` lo rechaza con `TypeError`) y `round(f, 4)` (redondea antes de tiempo y no es determinista entre escalas).

### Sin API, aplicación ni frontend

Ninguna operación del borrador OpenAPI lleva TKT-013 en `x-tickets`. El caso de uso y las rutas de la importación son de TKT-018.

## Experimentos previos

Ninguno se ejecutó al diseñar: esta sesión no tiene intérprete. Las afirmaciones sobre la API de openpyxl se consultaron con Context7 (documentación oficial, `openpyxl.readthedocs.io`); la documentación no sustituye al experimento. Los ejecuta la fila A0 (o B0) con un guion en el directorio temporal de la sesión, **nunca en el repositorio**, con `uv run --with openpyxl python <guion>` desde `backend/`, sin añadir la dependencia. La salida se pega en `impl.md` **sin descripciones de concepto ni precios del cliente** más allá de los que ya cita la spec.

| # | Afirmación | Experimento | Resultado esperado | Fuente |
|---|---|---|---|---|
| E-1 | Con `read_only=True, data_only=True`, una celda de error llega como la cadena `#REF!` | Libro sintético con `ws["E2"] = "#REF!"` (openpyxl la marca `data_type = "e"`) guardado y releído; y la celda E13 de Union | `'#REF!'` de tipo `str` en los dos | Stack §4.5; `_bind_value` de openpyxl (Context7) para el tipo `e`; la lectura `(sin ejecutar)` |
| E-2 | Los números llegan como `int` o `float`, nunca `Decimal` | Tipos de A13, D13 y E13 de ENITI, de A29 (`620040-A`) y de D12 de Union; `repr` de D13 | `int` en el código, `str` en `620040-A`, `float` en cantidad y precio; `repr` igual a `'16.089'` | `(sin ejecutar)`. Contradice la frase de `docs/06-stack-tecnologico.md:597`, en §12 «Lo que se descartó» («openpyxl devuelve `Decimal` o cadena») |
| E-3 | `iter_rows(values_only=True)` en solo lectura, tras `reset_dimensions()`, entrega una tupla por cada fila, también las vacías intermedias | Libro sintético con valores solo en las filas 3 y 7; contar tuplas y su posición. En ENITI, que la fila 13 enumerada sea `620001` | Siete tuplas, la 3 y la 7 con valor; el código de la fila 13 es `620001` | `(sin ejecutar)`. Si falla, variante B |
| E-4 | `ReadOnlyWorksheet.reset_dimensions()` existe y `iter_rows()` sin `max_row` recorre hasta la última fila después de llamarlo | Libro sintético cuya dimensión declarada se reescribe a `A1:A1` en el XML; leer con y sin `reset_dimensions()` | Sin la llamada, una fila; con ella, todas | Documentación «Read-only mode» (Context7) |
| E-5 | Cada archivo real tiene exactamente una hoja cuyo nombre normalizado empieza por `catalogo` | Listar `sheetnames` de los dos libros y aplicar la normalización de `elegir_hoja` | ENITI: solo `CATALOGO`; Union: solo `CATALOGO DE CONCEPTOS` | Spec, medición del 2026-11-02 `(sin ejecutar con esta regla)`. **Si hay otra candidata, se escala antes de A1** |
| E-6 | Patrón de corridas de ENITI 8 a 45 y de Union 8 a 20 | Volcar por fila: número, tipo y valor de la columna A, y tipo y valor de la B solo en filas sin código | Coincide con «La regla de profundidad». El volcado alimenta los patrones de TC-20 y TC-21 (con nombres neutros) y la tabla literal de TC-33 y TC-34 | `(sin ejecutar)` |
| E-7 | `openpyxl.cell.cell.ERROR_CODES` es exactamente el conjunto de `ERRORES_DE_FORMULA` | Imprimir la tupla | Los siete literales | `_bind_value` de openpyxl (Context7) muestra que existe; su contenido `(sin ejecutar)` |
| E-8 | Las cifras de la spec y el oráculo de profundidad se cumplen con la regla de este diseño | Prototipo de la regla en el guion sobre los dos libros: conceptos (5,028 y 4,281), unidades por valor normalizado (`CA-5`), `#REF!` en E y F de Union (8,562), filas de grupo con nombre `#REF!` (21), conceptos sin partida y sus filas, el conjunto de nombres por profundidad, corridas de más de cuatro filas, primer concepto de cada libro y suma de cantidad × precio unitario de ENITI | Cifras de la spec; conceptos sin partida solo en Union 12 a 16; todo nombre en `NIVEL` con forma `NIVEL n` o `ROOF GARDEN`; ninguna corrida de más de cuatro. Se anotan el vocabulario de `PARTIDA` y el total de ENITI, que fijan TC-36 y TC-41 | Spec `(sin ejecutar con esta regla)`. **Si el oráculo falla, se escala antes de A1** |
| E-9 | `types-openpyxl` existe y con él `uv run mypy .` acepta `load_workbook(…, read_only=True, data_only=True)`, `libro[nombre]`, `isinstance(hoja, ReadOnlyWorksheet)` y `hoja.reset_dimensions()`; la ruta de importación de `ReadOnlyWorksheet` | En B0, tras `uv add`, un módulo de prueba en el directorio temporal con esas llamadas | mypy sin errores; ruta `openpyxl.worksheet._read_only` | `(sin ejecutar)`. Si la clase no se exporta por una ruta pública, se importa de esa ruta privada con un comentario |
| E-10 | `CatalogoLeido` sobrevive a `pickle` con `Cantidad` y `Dinero` dentro, para el `ProcessPoolExecutor` de TKT-015 | `pickle.loads(pickle.dumps(catalogo)) == catalogo` sobre ENITI | Igualdad | `(sin ejecutar)`. Informativo: se anota para TKT-015, no es criterio |
| E-11 | Un `bool` y un `datetime` escritos con openpyxl se releen como `bool` y `datetime` | Libro sintético con `True` y `datetime(2026, 1, 1)` | Esos tipos | `(sin ejecutar)` |
| E-12 | openpyxl se instala con Python 3.14 y `pip-audit` no reporta vulnerabilidades en la versión fijada | En B0, `uv sync --locked --python 3.14` y el paso de `pip-audit` de `ci.yml` en local | Sin errores y sin vulnerabilidades | `(sin ejecutar)` |
| E-13 | Tiempo y memoria de leer cada archivo real | `time.perf_counter()` y `tracemalloc` alrededor de `leer_catalogo` | Se anotan en `impl.md` para TKT-015 | `(sin ejecutar)`. Informativo |
| E-14 | Con `defusedxml` instalado, openpyxl lo usa sin configuración | Solo si se aprueba P10: `from openpyxl.xml import DEFUSEDXML`, ejecutado en un entorno sin el grupo `dev` (`uv run --no-dev`), porque `defusedxml` ya está instalado como dependencia transitiva de `pip-audit` y en desarrollo daría `True` aunque P10 no se apruebe | `True` | Documentación de seguridad de openpyxl (Context7); la variable `(sin ejecutar)` |

## Orden de implementación

Se ejecuta fila por fila con el ciclo TDD de [metodología §16](../../metodologia.md#16--el-ciclo-tdd): rojo, verde, refactor. La verificación de cada paso corre **antes** de pasar al siguiente. Todas las órdenes, desde `backend/`.

### Entrega TKT-013a · dominio puro

| # | Paso | Tests que pone en verde | Agente | Modelo | Verificación | Estado |
|---|---|---|---|---|---|---|
| A0 | Experimentos E-1 a E-8 y E-11 con `uv run --with openpyxl` y un guion en el directorio temporal; salida en `impl.md`. Sin código del repositorio | — | `tester-backend` | `haiku` · tarea mecánica: el guion y lo esperado están escritos aquí | Cada resultado coincide con la columna «Resultado esperado». **Si E-5 o E-8 no coinciden, `/sdd-escalar` antes de A1** | Pendiente |
| A1 | `dominio/catalogo.py` completo (constantes, enumeraciones y los cinco objetos de valor) y, en `lectura_catalogo.py`, `normalizar_unidad`, `interpretar_numero` y `letra_de_columna`. ~110 líneas | TC-01 a TC-09 | `desarrollador-dominio` | `haiku` | `uv run pytest tests/test_tkt013_dominio.py -k "unidad or numero or letra or objetos"`; `uv run python -m herramientas.verificar_float` | Pendiente |
| A2 | `elegir_hoja`, `catalogo_sin_conceptos` y los pasos 1, 2 y 5 de `analizar_hoja` (encabezado, columnas y cierre sin conceptos). ~70 líneas | TC-10 a TC-17 | `desarrollador-dominio` | `haiku` | `uv run pytest tests/test_tkt013_dominio.py -k "esc27 or hoja or encabezado or columna"` | Pendiente |
| A3 | Pasos 3 y 4 de `analizar_hoja`: clasificación de filas, la regla de profundidad, los datos del concepto y sus hallazgos. ~120 líneas | TC-18 a TC-30 | `desarrollador-dominio` | `haiku` | `uv run pytest tests/test_tkt013_dominio.py` completo en verde | Pendiente |
| A4 | Cierre de a: mutantes M-01 a M-13 sobre el dominio; ficha de TKT-013 en `docs/05` (ver «Documentación afectada»); suite completa | Todos los de a, TC-INV-1 y TC-INV-2 | `tester-backend` | `sonnet` · valor por omisión del agente: la mutación es el oráculo del oráculo | Cada mutante aplicado, test en rojo, revertido, salida en `impl.md`; `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .`, `uv run lint-imports`, `uv run python -m herramientas.verificar_float`, `uv run pytest`; `python tools/verificar_docs.py` | Pendiente |

### Entrega TKT-013b · openpyxl, archivos reales y totales

| # | Paso | Tests que pone en verde | Agente | Modelo | Verificación | Estado |
|---|---|---|---|---|---|---|
| B0 | `uv add openpyxl`; `uv add --dev types-openpyxl` (y `uv add defusedxml` si se aprueba P10); `uv sync --locked --python 3.14`. Experimentos E-9, E-12 y E-14 | TC-INV-3 | `ingeniero-devsecops` | `haiku` · tarea mecánica verificable por comando (fijar una versión), bajada que prevé metodología §14.2 | `uv lock --check`; E-12 sin vulnerabilidades; `uv run mypy .` en verde | Pendiente |
| B1 | Sección «TKT-013» de `conftest.py` (`LibroCatalogo`, `libro_catalogo`, `archivo_eniti`, `archivo_union`) la escribe el tester en el rojo; `infraestructura/lector_catalogo.py` el desarrollador. ~60 líneas de producción | TC-31 a TC-40 y TC-INV-4 | `desarrollador-aplicacion` (carga `conv-backend-fastapi`, que cubre `infraestructura/`) | `haiku` | `uv run pytest tests/test_tkt013_lector.py tests/test_tkt013_archivos_reales.py`. En CI y en una máquina sin las variables, las de archivos reales salen `SKIPPED` con su motivo en el resumen de `-ra`; **en la máquina de la persona dueña, con las dos variables definidas, en verde** y la salida en `impl.md` | Pendiente |
| B2 | `dominio/totales_catalogo.py` (`S1`). ~35 líneas | TC-41 a TC-43 | `desarrollador-dominio` | `haiku` | `uv run pytest tests/test_tkt013_totales.py`, con las variables definidas | Pendiente |
| B3 | Documentación de b y ADR-033 (ver «Documentación afectada»). Sin código | — | `desarrollador-dominio` | `haiku` | `python tools/verificar_docs.py`; `python -m unittest discover -s tools/tests -v` | Pendiente |
| B4 | Experimentos E-10 y E-13 sobre los archivos reales; cifras en `impl.md` para TKT-015 | — | `tester-backend` | `haiku` · tarea mecánica | Cifras anotadas | Pendiente |
| B5 | Cierre de b: mutantes M-14 a M-18 y la suite completa con y sin las variables de entorno | Todos los de b y la regresión completa | `tester-backend` | `sonnet` · valor por omisión del agente | Cada mutante en rojo y revertido; todo el trabajo `backend` de `ci.yml` en verde en local, incluido `pip-audit` | Pendiente |

**Modelo:** `haiku` por omisión. Ninguna fila cae en un disparador de [metodología §14](../../metodologia.md#14--enrutamiento-de-modelo): no hay regla de dinero ni de límite (`RN-03` y afines), ni bloqueo, ni autorización, ni disparador, ni permisos de rol. La conversión del `float` es la regla 1 de `CLAUDE.md`, pero queda reducida a una línea escrita en este diseño. Las filas de cierre van en `sonnet` porque es el valor por omisión de `tester-backend`. Ninguna fila va en `opus`.

Estado: `Pendiente` · `✓ Hecho` · `⚠ Ajustado` (y el ajuste se documenta en `impl.md`).

## Plan de pruebas

Las pruebas del dominio (`tests/test_tkt013_dominio.py`) construyen las filas como tuplas con un ayudante local `fila(numero, *valores)` y un encabezado de prueba; no usan openpyxl ni base. Las de infraestructura (`tests/test_tkt013_lector.py`) construyen el libro con `LibroCatalogo` en `tmp_path`, con valores y nunca con fórmulas (una fórmula escrita por openpyxl no tiene valor en caché, y con `data_only` se leería `None`). Las de archivos reales (`tests/test_tkt013_archivos_reales.py`) usan `archivo_eniti` y `archivo_union`, que leen la ruta de `CIMENTA_CATALOGO_ENITI` y `CIMENTA_CATALOGO_UNION` y llaman a `pytest.skip("CIMENTA_CATALOGO_ENITI no está definida: la prueba contra el archivo real se omite (PA-T3)")` si la variable falta, o `pytest.skip("… no existe: …")` si la ruta no existe. **Ningún dato del cliente se copia al repositorio**: el libro sintético usa códigos y nombres inventados (`P-001`, `NIVEL A`, `ZONA 1`, `TRABAJO X`), con la misma forma que los reales.

Todo rechazo comprueba el hallazgo completo (`causa`, `hoja`, `fila`, `columna`, `valor_original` y, donde aplica, `detalle`) **y** que el campo afectado quedó `None` y no en cero.

### TKT-013a · dominio

| # | Caso | Tipo | Criterio | Escenario |
|---|---|---|---|---|
| TC-01 | `test_hdu001_esc08_unidades_admitidas_son_las_ocho_del_catalogo`: `UNIDADES_ADMITIDAS` igual al conjunto literal de las ocho | feliz | `CA-5` · invariante 27 | `HDU-001 esc. 8` |
| TC-02 | `test_hdu001_esc08_variantes_de_mayusculas_y_espacios_se_normalizan`, parametrizada: `Pza`, `pza`, `PZA` → `PZA`; `Ml` → `ML`; `" m2 "` → `M2` | feliz | `CA-5`, `CA-6` | `HDU-001 esc. 8` |
| TC-03 | `test_hdu001_esc08_grafia_ajena_al_catalogo_no_se_normaliza`, parametrizada: `M2.`, `M²`, `M 2`, `M3`, `""` → `None` | **rechazo** | `CA-6` · `PA-T12` | `HDU-001 esc. 8` |
| TC-04 | `test_hdu001_esc06_entero_y_decimal_llegan_como_tipos_base`: `interpretar_numero(16, Cantidad) == Cantidad(16)`; `interpretar_numero(Decimal("16.089"), Cantidad) == Cantidad("16.089")`; `interpretar_numero(Decimal("668.69"), Dinero) == Dinero("668.69")`; el `.valor` de cada uno es `Decimal` y no está cuantizado (`Decimal("16.089")` conserva tres decimales) | feliz | `CA-2`, `CA-12` | `HDU-001 esc. 6` |
| TC-05 | `test_hdu001_esc06_error_de_formula_no_es_cero`: `"#REF!"` y `" #N/A "` → `ERROR_DE_FORMULA`; el resultado no es `Dinero` | **rechazo** | `CA-7` | `HDU-001 esc. 6` |
| TC-06 | `test_hdu001_esc06_texto_en_columna_numerica_no_es_cero`: `"diez"` y `"$ 668,69"` → `NO_ES_NUMERO` | **rechazo** | `CA-8` | `HDU-001 esc. 6` |
| TC-07 | `test_hdu001_esc06_celda_vacia_no_es_cero`: `None` y `"   "` → `VALOR_AUSENTE` | **rechazo** | `CA-8` · P6 | `HDU-001 esc. 6` |
| TC-08 | `test_hdu001_esc06_numero_fuera_de_tipos_base_se_reporta`: `Decimal("1E-50")` y `Decimal("1E+45")` → `NO_ES_NUMERO`, sin excepción | **rechazo** y borde | `CA-8` | `HDU-001 esc. 6` |
| TC-09 | `test_hdu001_esc05_letra_de_columna`, parametrizada: `0 → A`, `4 → E`, `25 → Z`, `26 → AA`, `27 → AB` | borde | `CA-7` | `HDU-001 esc. 5` |
| TC-10 | `test_hdu001_esc05_la_hoja_del_catalogo_se_elige_sin_distinguir_mayusculas_ni_acentos`, parametrizada: `["APU 1", "CATALOGO"]` → `CATALOGO`; `["Catálogo de conceptos", "Resumen"]` → `Catálogo de conceptos` | feliz | `CA-1`, `CA-2` · `PA-T5` | `HDU-001 esc. 5` |
| TC-11 | `test_hdu001_esc27_libro_sin_hoja_de_catalogo`: `["APU 1", "RESUMEN"]` → `HOJA_NO_LOCALIZADA` con `detalle` que contiene `APU 1` y `RESUMEN`; `catalogo_sin_conceptos` da cero conceptos | **rechazo** | `CA-10` | `HDU-001 esc. 27` |
| TC-12 | `test_hdu001_esc27_dos_hojas_candidatas_no_se_elige_ninguna`: `["CATALOGO", "CATALOGO (2)"]` → `HOJA_AMBIGUA`, `detalle == "CATALOGO, CATALOGO (2)"` | **rechazo** | `CA-10` | `HDU-001 esc. 27` |
| TC-13 | `test_hdu001_esc27_hoja_sin_encabezado`: filas de metadatos sin `Código` en A → `ENCABEZADO_NO_LOCALIZADO` con `hoja` y `columna="A"`; cero conceptos; ninguna excepción | **rechazo** | `CA-10` | `HDU-001 esc. 27` |
| TC-14 | `test_hdu001_esc27_encabezado_sin_conceptos`: encabezado y tres filas de grupo → `NINGUN_CONCEPTO` con `fila` igual a la del encabezado; cero conceptos | **rechazo** | `CA-10` | `HDU-001 esc. 27` |
| TC-15 | `test_hdu001_esc05_encabezado_con_otras_mayusculas_y_rotulos`, parametrizada por los dos encabezados reales: `Código · ENCHAPES · Unidad · Cantidad · P.U. · IMPORTE` y `CODIGO · DESCRIPCION COMPLETA · UNIDAD · CANTIDAD · P.U. · IMPORTE · NOTAS`, en la fila 8 tras siete de metadatos → `fila_encabezado == 8`; la descripción sale de la columna B en los dos | feliz | `CA-1`, `CA-2` · `PA-T5`, `PA-T6` | `HDU-001 esc. 5` |
| TC-16 | `test_hdu001_esc27_columna_que_falta_o_se_repite`, parametrizada: sin `Unidad`; con `IMPORTE` dos veces → `COLUMNA_NO_LOCALIZADA` con `valor_original` igual al rótulo y `detalle` (`"no aparece"`, `"aparece 2 veces"`); cero conceptos | **rechazo** | `CA-10` · P8 | `HDU-001 esc. 27` |
| TC-17 | `test_hdu001_esc05_el_resultado_es_inmutable`: asignar un atributo de `CatalogoLeido` y de `ConceptoLeido` lanza `FrozenInstanceError`; `conceptos` y `hallazgos` son `tuple` | feliz | `CA-12` · `M4` | `HDU-001 esc. 5` |
| TC-18 | `test_hdu001_esc05_cada_fila_sin_codigo_es_un_nodo_y_nunca_un_concepto`: ningún `ConceptoLeido.fila` coincide con la de un nodo; el nombre se conserva tal cual, incluido un doble espacio y un espacio final | feliz | `CA-3` | `HDU-001 esc. 5` |
| TC-19 | `test_hdu001_esc05_primera_corrida_de_cuatro_llena_la_ruta`: corrida de cuatro y dos conceptos → ruta `RAIZ`, `NIVEL`, `AREA`, `PARTIDA` con sus filas | feliz | `CA-3` · `PA-T2` | `HDU-001 esc. 5` |
| TC-20 | `test_hdu001_esc05_patron_de_corridas_de_eniti`: las filas 9 a 45 de E-6 con nombres neutros y los mismos números de fila; cada concepto con la ruta que dicta la regla (tabla literal escrita desde E-6). Incluye la partida sola de la fila 15 y el área más partida de 27 y 28 | feliz | `CA-3` · `PA-T2` | `HDU-001 esc. 5` |
| TC-21 | `test_hdu001_esc05_patron_de_corridas_de_union_square`: las filas 9 a 20 de E-6 con nombres neutros; los conceptos 12 a 16 sin partida bajo la raíz, el nivel y el área de la corrida 9 a 11; el de la fila 19 bajo el área y la partida de 17 y 18 | feliz y **rechazo** | `CA-4`, `CA-9` · `PA-T2` | `HDU-001 esc. 5` |
| TC-22 | `test_hdu001_esc05_concepto_sin_partida_se_reporta_sin_inventarla`: un hallazgo `CONCEPTO_SIN_PARTIDA` por cada concepto 12 a 16, con `hoja` y `fila`; `ruta.partida is None`; ningún nodo nuevo creado | **rechazo** | `CA-9` · `PA-T13` | `HDU-001 esc. 5` |
| TC-23 | `test_hdu001_esc05_nombre_ilegible_conserva_su_posicion`: corrida `NIVEL B`, `#REF!`, `TRABAJO Y` antes de un concepto → el nodo de área tiene `nombre=None` y ocupa `AREA`; la partida es `TRABAJO Y`; hallazgo `NOMBRE_ILEGIBLE` con `columna="B"` y `valor_original="#REF!"` | **rechazo** | `CA-11` | `HDU-001 esc. 5` |
| TC-24 | `test_hdu001_esc05_filas_vacias_no_son_nodos_ni_cortan_la_corrida`: una fila de `None`, una de cadenas en blanco y una sin código ni nombre con un importe, entre dos filas de grupo → cero hallazgos y la ruta igual que sin ellas | feliz | `CA-11` · P5 · `PA-T7` | `HDU-001 esc. 5` |
| TC-25 | `test_hdu001_esc05_corrida_de_mas_de_cuatro_filas`: corrida de cinco posterior → la primera da `PROFUNDIDAD_EXCEDIDA` con su fila y nombre; las cuatro últimas forman la ruta | **rechazo** y borde | `CA-3` · `PA-T2` | `HDU-001 esc. 5` |
| TC-26 | `test_hdu001_esc05_corrida_final_sin_conceptos_se_descarta`: dos filas de grupo al final → no están en `nodos` y no dan hallazgo | borde | P5 | `HDU-001 esc. 5` |
| TC-27 | `test_hdu001_esc05_codigo_conserva_su_forma`: `620001` (`int`) → `"620001"`; `Decimal("620001.0")` → `"620001"`; `"620040-A"` → `"620040-A"`; `" 620002 "` → `"620002"` | feliz | `CA-1` | `HDU-001 esc. 5` |
| TC-28 | `test_hdu001_esc08_unidad_desconocida_se_conserva_y_se_reporta`: conceptos con `M2.` y `M²` → `unidad` igual al original y hallazgo `UNIDAD_NO_RECONOCIDA` con `columna="C"` y el valor original; uno con `" m2 "` → `M2` y sin hallazgo | **rechazo** | `CA-6` | `HDU-001 esc. 8` |
| TC-29 | `test_hdu001_esc06_ref_en_precio_e_importe_se_reporta_por_columna`: concepto con `#REF!` en E y F → dos hallazgos `ERROR_DE_FORMULA` (`columna` `E` y `F`, `valor_original="#REF!"`); `precio_unitario is None`, `importe is None`, `cantidad` intacta | **rechazo** | `CA-7` | `HDU-001 esc. 6` |
| TC-30 | `test_hdu001_esc06_texto_en_cantidad_y_precio_se_reporta_por_columna`: cantidad `"diez"` y P.U. `"$ 668,69"` → hallazgos en D y E con esos valores; los dos campos `None`; el concepto sigue en `conceptos` con su ruta | **rechazo** | `CA-8` | `HDU-001 esc. 6` |
| TC-INV-1 | `lint-imports` en verde: `dominio-sin-framework` y `solo-por-interfaz` sin violaciones con los módulos nuevos | regresión | `CA-R1` | reglas 2 y 3 |
| TC-INV-2 | `verificar_float` en verde sobre `cimenta/presupuesto/dominio/` | regresión | `CA-R2` | regla 1 |

### TKT-013b · infraestructura, archivos reales y totales

| # | Caso | Tipo | Criterio | Escenario |
|---|---|---|---|---|
| TC-31 | `test_hdu001_esc05_libro_sintetico_con_la_forma_de_eniti`: libro con hojas `APU 1` y `CATALOGO` (encabezado de ENITI en la fila 8, corrida de cuatro, `P-040-A`) → hoja `CATALOGO`, conceptos en orden, rutas, cantidad `Cantidad("16.089")` desde el `float` 16.089 | feliz | `CA-1`, `CA-3` | `HDU-001 esc. 5` |
| TC-32 | `test_hdu001_esc06_libro_sintetico_con_la_forma_de_union_square`: hoja `CATALOGO DE CONCEPTOS`, `#REF!` en E y F de cada concepto, una fila de grupo `#REF!`, un área sin partida al principio → los hallazgos de `CA-7`, `CA-9` y `CA-11` con hoja, fila, columna y valor | **rechazo** | `CA-7`, `CA-9`, `CA-11` | `HDU-001 esc. 6` |
| TC-33 | `test_hdu001_esc05_rutas_reales_de_eniti` (real): las tres rutas de `CA-3` y la tabla literal de las filas 9 a 45 que dejó E-6 | feliz | `CA-3` | `HDU-001 esc. 5` |
| TC-34 | `test_hdu001_esc05_rutas_reales_de_union_square` (real): ruta del concepto de la fila 19 (`CA-4`) y tabla literal de las filas 9 a 20 | feliz | `CA-4` | `HDU-001 esc. 5` |
| TC-35 | `test_hdu001_esc05_lee_el_catalogo_de_eniti` y `test_hdu001_esc05_lee_el_catalogo_de_union_square` (reales): hoja, `fila_encabezado == 8`, 5,028 y 4,281 conceptos en orden de fila, primer concepto (`620001` fila 13, `M2`, `Cantidad("16.089")`, `Dinero("668.69")`; `620012` fila 12), `620040-A` fila 29, cantidades `Cantidad`; con `iter_rows` de `ReadOnlyWorksheet` envuelto por `monkeypatch`, el único título leído es el de la hoja del catálogo | feliz | `CA-1`, `CA-2` | `HDU-001 esc. 5` |
| TC-36 | `test_hdu001_esc05_oraculo_de_profundidad_en_los_archivos_reales` (real): todo nodo `NIVEL` cumple `^(nivel\s+\d+\|roof garden)$` sin distinguir mayúsculas; todo nodo `PARTIDA` está en el vocabulario de E-8; ningún `PROFUNDIDAD_EXCEDIDA`; `CONCEPTO_SIN_PARTIDA` solo en Union filas 12 a 16 | feliz y **rechazo** | `CA-3`, `CA-4`, `CA-9` · `PA-T2` | `HDU-001 esc. 5` |
| TC-37 | `test_hdu001_esc08_unidades_reales_normalizadas` (real): conteos de `CA-5` y ningún `UNIDAD_NO_RECONOCIDA`. `test_hdu001_esc06_ref_real_de_union_square`: 8,562 `ERROR_DE_FORMULA` en E y F, el de la fila 13 columna E con hoja `CATALOGO DE CONCEPTOS`, ninguno en D, 4,281 conceptos con cantidad. `test_hdu001_esc05_nombres_ilegibles_reales`: 21 `NOMBRE_ILEGIBLE` en la columna B | **rechazo** | `CA-5`, `CA-7`, `CA-11` | `HDU-001 esc. 6` y `esc. 8` |
| TC-38 | `test_hdu001_esc27_libro_sintetico_sin_catalogo_ni_encabezado_ni_conceptos`, parametrizada por los tres libros de `CA-10` y uno con dos hojas candidatas: `leer_catalogo` devuelve el hallazgo de estructura y no lanza | **rechazo** | `CA-10` | `HDU-001 esc. 27` |
| TC-39 | `test_hdu001_esc06_valores_de_celda_que_no_son_numero`: en el libro sintético, `True` en la cantidad, un `datetime` en el P.U., un hueco de filas vacías entre la 9 y la 14 → `NO_ES_NUMERO` con `"TRUE"` y el texto de la fecha; los números de fila de los conceptos posteriores al hueco son los reales | **rechazo** y borde | `CA-8` | `HDU-001 esc. 6` |
| TC-40 | `test_hdu001_esc05_leer_no_escribe_ni_usa_float` (sintético con `base_de_prueba`; y real): `inspect.signature(leer_catalogo)` tiene un solo parámetro, `contenido`; ningún módulo nuevo importa `sqlalchemy` ni `psycopg` (por `ast`); `nivel`, `area`, `partida` y `concepto` siguen en cero filas con el rol de aplicación antes y después; todo `.valor` es `Decimal` y ningún atributo es `float`; dos lecturas del mismo contenido dan resultados iguales | feliz | `CA-12` | `HDU-001 esc. 5` |
| TC-41 | `test_hdu001_esc05_totales_de_eniti` (real): niveles, áreas, partidas y conceptos de E-8; `importe.cuantizar()` igual al total medido en E-8 | feliz | `CA-13` | `HDU-001 esc. 5` |
| TC-42 | `test_hdu001_esc05_importe_no_calculable_nunca_es_cero` (real Union y sintético): `importe is None`; también con un solo concepto sin P.U. entre diez | **rechazo** | `CA-13` · P7 | `HDU-001 esc. 5` |
| TC-43 | `test_hdu001_esc05_importe_de_concepto_es_cantidad_por_precio`: `importe_calculado` de `Cantidad("16.089")` y `Dinero("668.69")` es `Dinero("10758.55341")` sin cuantizar; `None` si falta uno | feliz y **rechazo** | `CA-13` | `HDU-001 esc. 5` |
| TC-INV-3 | `pip-audit` sin vulnerabilidades y `uv lock --check` en verde | regresión | `CA-R3` | — |
| TC-INV-4 | `test_tkt013_car1_constantes_sincronizadas`: `UNIDADES_ADMITIDAS` igual a los valores de `pg_get_constraintdef` de `ck_concepto_unidad` (rol de migración, que lee el catálogo); `ERRORES_DE_FORMULA` igual a `set(openpyxl.cell.cell.ERROR_CODES)` | regresión | `CA-5`, `CA-7` · invariante 27 | — |

No hay prueba de concurrencia: el lector no bloquea ni escribe.

### Mutación

Cada mutante se aplica a mano, se ejecuta la prueba indicada, se ve en rojo y se revierte. Lo que se mutó y qué cayó se pega en `impl.md`.

| # | Mutante | Test que debe ponerse rojo |
|---|---|---|
| M-01 | La primera corrida se alinea a la partida, como las demás | TC-21 y TC-22 |
| M-02 | Toda corrida se alinea a la raíz | TC-20 (fila 15) |
| M-03 | Una fila vacía corta la corrida | TC-24 |
| M-04 | La fila de grupo con nombre `#REF!` se salta en vez de ocupar su posición | TC-23 |
| M-05 | `interpretar_numero` devuelve `tipo(0)` ante un error de fórmula | TC-05 y TC-29 |
| M-06 | `interpretar_numero` devuelve `tipo(0)` ante una celda vacía | TC-07 |
| M-07 | `normalizar_unidad` quita también los puntos (`replace(".", "")`) | TC-03 y TC-28 (`M2.`) |
| M-08 | `normalizar_unidad` sin `strip()` | TC-02 y TC-28 (`" m2 "`) |
| M-09 | `elegir_hoja` toma la primera candidata cuando hay varias | TC-12 |
| M-10 | Sin el hallazgo `CONCEPTO_SIN_PARTIDA` | TC-22 |
| M-11 | Rótulo del encabezado normalizado sin quitar acentos | TC-15 (`Código`) |
| M-12 | La descripción se busca por rótulo en lugar de a la derecha del código | TC-15 (`ENCHAPES`) |
| M-13 | Con más de cuatro filas se aplican las cuatro primeras | TC-25 |
| M-14 | `Decimal(valor)` en lugar de `Decimal(repr(valor))` | TC-31 (16.089) |
| M-15 | `Decimal(str(round(valor, 2)))` | TC-31 y TC-35 (16.089) |
| M-16 | `bool` se comprueba después de `int` | TC-39 |
| M-17 | `totalizar` devuelve `Dinero(0)` cuando algún importe falta | TC-42 |
| M-18 | Sin `reset_dimensions()`, con el libro de dimensión reescrita de E-4 | TC-39 (añadirle ese libro si E-4 lo confirma) |

## Impacto

Análisis del arquitecto; `revisor-impacto` lo revisa antes del gate.

| Qué se toca | Quién depende | Riesgo | Mitigación |
|---|---|---|---|
| `backend/pyproject.toml` y `uv.lock` (b) | Todo el trabajo `backend` de CI | Una dependencia nueva con vulnerabilidad o sin rueda para 3.14 | E-12 en B0 antes de escribir código |
| `uv run mypy .` (b) | Todo el backend | Sin `types-openpyxl`, `import-untyped` | `types-openpyxl` en `dev`; E-9 |
| `conftest.py`, sección «TKT-013» (b) | Todas las pruebas | Una fixture con `autouse` alteraría pruebas ajenas | Sin `autouse`, como `DatosPresupuesto` |
| Variables `CIMENTA_CATALOGO_ENITI` y `CIMENTA_CATALOGO_UNION` (b) | Pruebas locales | Una ruta mal escrita omite en silencio | El `skip` dice qué variable y qué ruta; `-ra` lo muestra en el resumen; B1 exige la salida en verde con las variables en `impl.md` |
| `CatalogoLeido` como contrato interno (a) | TKT-014, TKT-015, TKT-017 y TKT-018 | Cambiar sus campos obliga a tocar a los cuatro | Inmutable y tipado; E-10 deja anotado que viaja por `pickle` |
| Códigos repetidos (`PA-T1`) | TKT-015 y TKT-017 | El lector devuelve todas las apariciones; el invariante 13 las rechazará al materializar | Fuera de este ticket: escalado en la spec |
| Raíz sin tabla (P3) | TKT-017 | No hay dónde materializar la raíz | Pregunta P3; el lector la conserva y no decide |

**Fronteras entre módulos:** No. Todo el código nuevo vive en `presupuesto`; `dominio/` solo importa la biblioteca estándar y `tipos_base`; `infraestructura/` importa `dominio/` y openpyxl; nada se publica en `interfaz.py`. Los quince contratos de `import-linter` no cambian.

## Documentación afectada

| Documento | Qué cambia | Ticket |
|---|---|---|
| `docs/05-tickets-trabajo.md`, ficha de TKT-013 (`:622`) | El primer criterio dice «a partir de la indentación y de las filas sin código»: pasa a «a partir de la posición de las filas sin código», y «deposita el resultado en la zona de preparación» pasa a «devuelve el resultado en memoria» (`PA-T11`). Subsección «Partición en dos tickets hermanos» con la tabla de este diseño | a |
| `docs/05-tickets-trabajo.md`, ficha de TKT-014 (`:644`) | «Depende de TKT-013» pasa a «Depende de TKT-013b». Es otra ficha, no la de TKT-013 | a |
| `docs/06-stack-tecnologico.md` | La fila de `:597` (§12, «Lo que se descartó»: «pandas para leer Excel») dice que «openpyxl devuelve `Decimal` o cadena»: devuelve `int`, `float` o cadena (E-2), y la frontera de infraestructura convierte el `float` con `Decimal(repr(…))`. §4.5 (`:201-209`) enlaza a ADR-033. Si se aprueba P10, `:79`, `:223` y `docs/05:534` asignan `defusedxml` a TKT-059: se anota que TKT-013b ya la declara | b |
| `sdd/_evolucion.md` y `sdd/tickets/tkt-013/_index.md` | Observaciones de cada entrega en la evolución. El índice pasa de una rama a dos (`tkt-013a-…` y `tkt-013b-…`) y su log recoge la partición, como en TKT-010 y TKT-011 | a y b |
| `docs/arranque-local.md` | Cómo definir `CIMENTA_CATALOGO_ENITI` y `CIMENTA_CATALOGO_UNION` en PowerShell para correr las pruebas contra los archivos reales, y que sin ellas se omiten | b |
| `docs/adr/` y `docs/adr/README.md` | ADR-033 con su fila en el índice | b |
| `CLAUDE.md` (`:14`), `README.md` (`:30` y `:262`) y `llms.txt` (`:27`) | El conteo «32 decisiones» pasa a 33 en las cuatro apariciones. `verificar_docs.py` no comprueba esta cifra: la fila B3 corre un `Grep` de «32» y pega la salida en `impl.md`. El cambio de `CLAUDE.md` lo aprueba la persona dueña (P11) | b |

**Observaciones del impacto que el ejecutor debe respetar.** (1) `verificar_docs.py` falla antes de A0 por los enlaces a `impl.md`; A0 crea ese archivo antes de correrlo. (2) Las docstrings de TKT-013a no citan ADR-033, que lo crea TKT-013b. (3) El nombre del ADR lleva la fecha real de B3. (4) TC-INV-4 parsea la forma `ANY (ARRAY[…])` de `pg_get_constraintdef`, y la unidad vive también en `ck_insumo_unidad`. (5) El lector devuelve cantidades, precios e importes negativos sin hallazgo, y el esquema los rechaza (`ck_concepto_*_no_negativo`): lo debe tener presente TKT-015 o TKT-017. (6) `Hallazgo` ya es el nombre de una clase en `herramientas/verificar_float.py:30`; no se importan entre sí, así que no hay colisión.
| `sdd/tickets/tkt-013/spec.md` | Los ajustes de «Criterios de la spec que hay que ajustar», si se aprueba P1; `PA-T2` y `PA-T9` pasan a resueltas con la referencia a este diseño | a |

## ¿Merece ADR?

Sí, uno, en formato MADR, creado en la fila B3:

- **ADR-033** · `docs/adr/20261102-lectura-posicional-del-catalogo.md`. Un recién llegado preguntará por qué la primera corrida se alinea distinto de las demás, por qué el lector no reconoce los niveles por su nombre y por qué el número pasa por `repr`. Opciones de profundidad: alinear todas las corridas a la partida, todas a la raíz, reconocer por nombre (`NIVEL n`), contar la profundidad máxima del archivo, y la elegida. Opciones de conversión: `Decimal(f)`, `round`, leer el XML de la celda sin openpyxl, y `Decimal(repr(f))`. Consecuencias: el límite conocido y su oráculo, y que el resultado vive en memoria sin persistencia (`PA-T11`).

La partición en dos tickets no necesita ADR: queda en la ficha de `docs/05`, como TKT-011.

## Pasada adversarial

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | La regla de corridas lee mal, en silencio, un área sin partida que no sea la primera de la hoja | Se declara como límite conocido, la prueba de oráculo TC-36 la vigila en los dos archivos completos y E-8 la mide antes de escribir código; si aparece, se escala. P4 pide aceptarla |
| 2 | Alta | Las cifras de `CA-1` (`16.089`, `668.69`) dependen de que el `float` guardado tenga esa representación más corta; si es `16.089000000000002`, el criterio falla sin defecto en el lector | E-2 lo mide en A0; si difiere, el criterio se ajusta con la persona dueña antes de B1, no se cambia la conversión |
| 3 | Media | `iter_rows` en solo lectura podría no entregar las filas vacías, y los números de fila de todos los hallazgos saldrían corridos | E-3 lo comprueba; la variante B queda decidida; TC-39 pone un hueco de filas en el libro sintético |
| 4 | Media | Un `bool` es `int` en Python: sin guarda, `Cantidad(True)` lanza `TypeError` y la excepción escapa del lector, contra `CA-10` | `_a_valor_celda` comprueba `bool` primero; TC-39 y M-16 |
| 5 | Media | Las pruebas de dominio con los patrones reales copiarían nombres de áreas y departamentos del cliente al repositorio público | TKT-013a usa nombres neutros con el mismo patrón de corridas; solo TKT-013b, contra los archivos que no se versionan, compara nombres reales, y únicamente los que la spec ya cita o los de E-6 |
| 6 | Media | Duplicar las ocho unidades en Python crea una segunda fuente que puede divergir del `CHECK` del invariante 27 | TC-INV-4 las compara con `pg_get_constraintdef` en cada ejecución |
| 7 | Baja | openpyxl no se protege por omisión de la expansión de entidades XML, y el lector abre un ZIP que viene de fuera | P10. La validación de TKT-059 limita el tamaño, pero no inspecciona las hojas |
| 9 | Alta | La regla supone que la primera corrida empieza en la fila de título. Un catálogo sin fila de título leería sus tres primeras filas (`nivel`, `área`, `partida`) como `raíz`, `nivel`, `área`, también en silencio. Los dos archivos reales la traen, pero un tercer formato (el README nombra uno más, `PA-T4`) puede no traerla | Se añade al «Límite conocido» y TC-36 la vigila: el nodo en posición `RAIZ` no puede llamarse `NIVEL n`. La persona dueña lo acepta en P4 con ese alcance |
| 10 | Media | El diseño lleva 11 filas y 18 mutantes para un lector de unos 400 líneas de producción; el coste de revisión puede superar al riesgo que cubre | Se mantiene: la mutación es el único oráculo contra el error silencioso de profundidad. El recorte previsto es `S1` vía `/sdd-escalar`, no los mutantes |
| 8 | Baja | `CA-12` («no abre una conexión») se probaría en verde aunque el lector no exista si solo se cuentan filas | TC-40 añade la firma y el análisis de imports por `ast` |

## Riesgos

| Riesgo | Probabilidad | Impacto | Qué se hace |
|---|---|---|---|
| E-5 encuentra una segunda hoja candidata en un archivo real | Baja | Alto: `CA-1` o `CA-2` no se cumplen con `PA-T5` | `/sdd-escalar` antes de A1, con los nombres encontrados |
| E-8 encuentra una estructura que la regla de corridas lee mal | Media | Alto: jerarquía mal armada | `/sdd-escalar` antes de A1; no se adapta la regla en ejecución |
| `types-openpyxl` no tipa `reset_dimensions` o `ReadOnlyWorksheet` | Media | Bajo | Un `cast` o un `# type: ignore[attr-defined]` con su motivo, decidido en B0 y anotado |
| El tamaño de cada PR (~735 y ~720) sigue por encima del tope | Cierta | Medio | Precedente de TKT-011; el recorte posible es `S1` (~100 líneas de b), vía `/sdd-escalar` |
| La variante B de E-3 cambia el ritmo de lectura | Baja | Bajo | E-13 mide el tiempo; TKT-015 decide si importa |

## Preguntas para el gate

| # | Pregunta | Recomendación |
|---|---|---|
| P1 | ¿Se parte en TKT-013a (dominio) y TKT-013b (openpyxl, reales y `S1`), con un PR cada uno y fusión a → b? | Sí: ~1,455 líneas en un PR triplican el tope; el precedente es TKT-011 |
| P2 | ¿Se confirma `PA-T9`: el `float` se convierte con `Decimal(repr(f))`, sin redondear, y `cuantizar()` queda para la materialización? | Sí: es exacta respecto de lo que openpyxl entrega, determinista, y no pierde información antes de tiempo |
| P3 | La fila de título (`ACABADOS EN MUROS Y PLAFONES`) es un cuarto nivel de agrupación, por encima del nivel, que el modelo no tiene. ¿Se conserva en el resultado como `RAIZ` y se deja a TKT-017 qué hacer con ella? ¿Se acepta el nombre «raíz», que no está en el glosario? | Sí a las dos: el lector no decide qué se materializa, y un nombre de glosario lo puede fijar TKT-017 cuando la materialice o la descarte |
| P4 | ¿Se acepta la regla de profundidad (cuatro niveles; primera corrida a la raíz, las demás a la partida) con su límite conocido vigilado por el oráculo? | Sí: es la única lectura que cuadra con las dos estructuras reales sin depender de nombres (`CA-4`) |
| P5 | Las filas sin código y sin nombre se ignoran sin hallazgo aunque traigan otros valores (subtotales); las vacías no cortan una corrida; una corrida al final sin conceptos se descarta sin hallazgo. ¿De acuerdo? | Sí: coincide con `PA-T7` (los importes de grupo no se leen) y con `CA-11` |
| P6 | Una celda vacía en la descripción, la unidad, la cantidad, el P.U. o el importe de un concepto da `VALOR_AUSENTE`; un `bool` o una fecha en una columna numérica dan `NO_ES_NUMERO`. ¿De acuerdo? | Sí: `M5` pide reportar lo que no se puede interpretar, y un dato que falta no se puede materializar |
| P7 | El importe total de `S1` es «no calculable» si **algún** concepto no tiene importe calculable, no solo si ninguno lo tiene. ¿De acuerdo? | Sí: un total parcial presentado como total es la misma mentira que el cero |
| P8 | Un rótulo de columna que falta o se repite deja el resultado sin conceptos, con un hallazgo de estructura, en vez de tomar la primera aparición. ¿De acuerdo? | Sí: mismo criterio que la hoja ambigua de `CA-10`; no se elige al azar |
| P9 | La unidad solo se normaliza por `strip()` y mayúsculas: `M 2` (espacio interior) no se reconoce. ¿De acuerdo? | Sí: es la lectura literal de `PA-T12` |
| P10 | ¿Se añade `defusedxml` como dependencia en TKT-013b, para que openpyxl no expanda entidades XML de un libro construido a propósito? | Sí: una línea en `pyproject.toml`, ningún código, y cierra un hueco que la dependencia nueva abre. Si se prefiere no ampliar el alcance, ticket propio antes de TKT-018 |
| P11 | ¿Se aprueba ADR-033 y editar el conteo de ADR en `CLAUDE.md`, `README.md` y `llms.txt`? | Sí, en TKT-013b |
