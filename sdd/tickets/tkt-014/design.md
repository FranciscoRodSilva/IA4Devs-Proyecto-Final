# Design · TKT-014 · Lector de análisis de precios unitarios

> [← index](_index.md) | [← spec](spec.md) | Siguiente: `impl.md` (lo escribe `/sdd-ejecutar`)

## Estrategia

El lector repite la forma de TKT-013: **todo lo que decide vive en `dominio/`** y recibe filas ya extraídas como tuplas de `ValorCelda`; **`infraestructura/` solo abre el libro con openpyxl**, entrega las filas de cada hoja y convierte el `float` con `Decimal(repr(f))` en la frontera, con el mismo `_a_valor_celda` de TKT-013. Cada hoja se lee como una máquina de estados sobre el rótulo de la columna A: la fila del rótulo cambia de bloque (`MATERIAL`, `MANO DE OBRA`, `COSTO DIRECTO`, viáticos, `PRECIO UNITARIO`), y dentro de cada bloque las columnas son constantes (`D`, `E`, `F`, `G`). Las filas se encuentran por rótulo, y las columnas son fijas porque la spec fija las mismas letras en las 44 hojas.

El P.U. se reconstruye **sumando lo leído**: cargo de cada insumo más importe de cada cargo, incluido el desconocido (`SIROC`), con `sumar()` de `tipos_base`, que es exacto. No se recalcula ninguna fórmula: ni `costo × rendimiento` (`PA-T6`) ni `porcentaje × base`. Por eso **no hace falta `Dinero × Rendimiento`**. La comparación con la tolerancia de ±0.01 se hace en el dominio sobre `Decimal`, que la biblioteca estándar compara exacto. `tipos_base` no se toca.

El libro se abre **una sola vez** en una función nueva, `leer_libro_presupuesto`, que comparte con `leer_catalogo` un ayudante privado extraído de su cuerpo. `leer_catalogo` conserva su firma y su comportamiento (`CA-R3`). La asociación con el catálogo y los insumos por crear son funciones puras del dominio que reciben el `CatalogoLeido` ya leído y un mapa de insumos existentes. Nada se publica en `cimenta.presupuesto.interfaz`.

El orden suma unas **1,765 líneas**, más de cuatro veces el tope de unas 400 por cambio: es la **condición de parada 3**. Se propone partir en **TKT-014a** (dominio de la hoja: lectura, totales y cuadre) y **TKT-014b** (asociación, insumos por crear, adaptador openpyxl, archivos reales y documentación), con un PR cada uno y fusión a → b, como TKT-013.

## Partición propuesta (condición de parada 3)

| Ticket | Musts | Contenido | Líneas estimadas | Depende de | Filas |
|---|---|---|---|---|---|
| TKT-014a | `M1` a `M4`, `M7` y `M8` sobre filas en memoria; `M9` en su parte (cifras en `Decimal`); `S1` | `dominio/analisis.py` (objetos de la hoja), las causas nuevas de lectura en `catalogo.py`, la ampliación de `interpretar_numero`, `dominio/lectura_analisis.py`, `herramientas/soporte_tkt014.py` y sus pruebas puras | ~830 (≈ 390 de producción, ≈ 430 de pruebas, ≈ 10 de documentación) | TKT-013b (archivado) | A0 a A5 |
| TKT-014b | `M5`, `M6`; `M1` a `M9` contra el libro real; `CA-R3` | `dominio/asociacion_analisis.py`, los objetos del libro en `analisis.py`, las causas de asociación e insumos, el refactor de `infraestructura/lector_catalogo.py` con `leer_libro_presupuesto`, las pruebas sintéticas con openpyxl y las de archivos reales, ADR-034 y la documentación | ~935 (≈ 175 de producción, ≈ 660 de pruebas, ≈ 100 de documentación) | TKT-014a | B1 a B5 |

**El orden de fusión es fijo: a → b.** TKT-014 queda como paraguas, conserva la spec y este diseño, y se cierra cuando se cierran los dos. TKT-015, TKT-016 y TKT-017 dependen de TKT-014b.

**Por qué esta frontera.** TKT-014a no lee ningún archivo ni toca openpyxl: sus pruebas alimentan al dominio con tuplas. Contiene lo más delicado (la máquina de estados y el cuadre) y se revisa sola. TKT-014b es el único que abre libros, el único que necesita los archivos reales y el único que cambia código de TKT-013.

**Alternativas descartadas.** Partir en tres (hoja · asociación e insumos · adaptador): el tramo central tendría unas 360 líneas, pero el tercero quedaría sin nada que probar en dominio y cada PR añade la ceremonia completa de revisión y fusión. Recortar `S1`: los totales son el mismo cálculo que exige el cuadre de `M7`; quitarlos ahorra unas 20 líneas, no un PR.

### Criterios de la spec que hay que ajustar si se aprueba la partición

| Criterio | Dice hoy | Debe decir |
|---|---|---|
| `CA-1`, `CA-2`, `CA-5`, `CA-7`, `CA-8`, `CA-9`, `CA-12` | Contra los archivos reales | Solo TKT-014b. TKT-014a cubre la lectura de la hoja con filas en memoria |
| `CA-3`, `CA-4`, `CA-6`, `CA-16` | Hoja real `MURO STD-635-STD` | TKT-014a con una hoja sintética de la misma forma y cifras neutras; TKT-014b contra el archivo real |
| `CA-10`, `CA-11`, `CA-13` | Libro u hoja sintética | TKT-014a con filas en memoria; TKT-014b repite `CA-10` (las 44 hojas reales) |
| `CA-14` | Dos hojas sintéticas | Solo TKT-014b (necesita varias hojas leídas) |
| `CA-15` | Base migrada y archivos reales | TKT-014a: cifras en `Decimal`; TKT-014b: base intacta y lectura determinista |
| `CA-R3` | Pruebas de TKT-013 | Solo TKT-014b: es el único que toca `lector_catalogo.py` |

## Escalera de decisión

| Objeto | Peldaño donde paró | Por qué |
|---|---|---|
| Abrir el libro dos veces (`leer_catalogo` y un lector de APU independientes) | 1 · descartado | El encargo pide una sola apertura y `CA-R3` la nombra. Cada apertura vuelve a descomprimir el libro y a analizar `sharedStrings`, y el de ENITI tiene 5,028 conceptos |
| `_leer_catalogo_de_libro(libro)` y `_filas(hoja)` en `lector_catalogo.py` (b) | 4 · cambio mínimo | Se extraen del cuerpo actual de `leer_catalogo` sin cambiar una sola instrucción; `leer_catalogo` las llama y conserva su firma `(contenido: bytes)`. No toca ningún invariante: es código de TKT-013, vigilado por su suite completa |
| `leer_libro_presupuesto(contenido, insumos_existentes)` (b) | 5 · objeto nuevo | Único punto que abre el libro una vez y entrega catálogo y análisis juntos. Vive en el mismo `lector_catalogo.py` para que openpyxl siga en un solo archivo (ADR-033) |
| Un archivo de infraestructura nuevo para los APU | 1 · descartado | Repetiría `load_workbook`, el manejo de errores y `_a_valor_celda`, o importaría privados entre archivos |
| `dominio/analisis.py`: `TipoInsumo`, `TipoCargo`, `CabeceraLeida`, `InsumoLeido`, `CargoLeido`, `TotalesAnalisis`, `AnalisisLeido` (a) | 5 · objeto nuevo | `M9` exige un valor en memoria y no existe ninguno para el análisis. `TipoCargo` lleva los siete valores de `ck_apu_cargo_tipo` y una prueba los sincroniza (TC-INV-4) |
| `InsumoPorCrear`, `AsociacionLeida`, `AnalisisDelLibro` (b) | 5 · objeto nuevo | `M5` y `M6` piden la asociación y los insumos por crear como dato; `AnalisisDelLibro` es el resultado único que devuelve el adaptador |
| `Hallazgo` | 3 · reuso | Tiene exactamente los campos que pide `M8`: causa, hoja, fila, columna, valor original y detalle |
| Diez causas nuevas en `CausaHallazgo` (cinco en a, cinco en b) | 4 · cambio mínimo | Añadir miembros a un `StrEnum` no altera los existentes ni el comportamiento de `leer_catalogo` (ninguna prueba enumera la clase). Un segundo enum obligaría a un segundo `Hallazgo`, porque `Hallazgo.causa` está tipado `CausaHallazgo`. No toca ningún invariante |
| `interpretar_numero` admite `Rendimiento` y `Porcentaje` (a) | 4 · cambio mínimo | Se amplía la restricción del parámetro de tipo de `(Cantidad, Dinero)` a `(Cantidad, Dinero, Rendimiento, Porcentaje)`. El cuerpo no cambia: los cuatro tipos se construyen igual |
| Rendimiento como `Rendimiento` (`NUMERIC(18,6)`) y porcentaje como `Porcentaje` (`NUMERIC(9,6)`); costo, cargo, base, importe y P.U. como `Dinero` | 3 · reuso de `tipos_base` | Son las columnas de `apu_insumo` y `apu_cargo`. Los cuatro tipos conservan la precisión completa hasta `cuantizar()`, que queda para TKT-017 |
| `Dinero × Rendimiento` en `tipos_base` | 1 · YAGNI, fuera | El cuadre suma el cargo leído; no multiplica. `PA-T11` de TKT-004 sigue abierto para TKT-016, que sí multiplica |
| Comparación con tolerancia en `tipos_base` | 2 · nativo | `abs(diferencia.valor) <= Decimal("0.01")`: `Decimal` compara exacto y la resta de `Dinero` ya es exacta. Un solo consumidor y una tolerancia que la spec declara supuesto del lector (`PA-T10`) no justifican API pública en `tipos_base` |
| `normalizar_clave_insumo` (a) | 5 · objeto nuevo | Decisión 1 de la persona dueña. `" ".join(texto.split()).upper()` es biblioteca estándar; la función existe para que el lector y quien arme las claves existentes (TKT-017) usen la misma |
| `normalizar_codigo` (a) | 3 · reuso | `_como_texto` de `lectura_catalogo.py` (entero, `Decimal` entero y cadena recortada) más `.upper()` (`PA-T4`) |
| `_normalizar_rotulo`, `_como_texto`, `_texto_original`, `_celda_vacia`, `letra_de_columna`, `normalizar_unidad`, `ERRORES_DE_FORMULA`, `UNIDADES_ADMITIDAS` | 3 · reuso | Ya resuelven acentos, mayúsculas, espacios, puntos, unidades y literales de error. Los cuatro privados se importan desde el módulo hermano del mismo paquete y la misma capa; renombrarlos tocaría TKT-013 sin cambiar comportamiento |
| Fecha como `datetime.date` en el dominio | 1 · descartado | La regla 2 de `CLAUDE.md` y ADR-021 excluyen `datetime` de `dominio/`. La fecha viaja como cadena ISO `AAAA-MM-DD`; TKT-017 la convierte |
| Cambiar `_a_valor_celda` para entregar fechas | 1 · descartado | Cambiaría lo que `leer_catalogo` reporta para una fecha en una columna numérica (TC-39 de TKT-013). El dominio lee la cadena `str(datetime)` que ya entrega |
| Puerto del lector, caso de uso en `aplicacion/`, exportar en `interfaz.py` | 1 · YAGNI, fuera | Igual que en TKT-013: el dominio no llama a la infraestructura, no hay transacción, y los consumidores (TKT-015 a TKT-018) son de `presupuesto` |
| Migración, `ck_apu_cargo_tipo` con `SIROC` | 1 · Won't | Decisión 6 de la persona dueña; ticket futuro |
| Dependencia nueva | 1 · ninguna | openpyxl y defusedxml ya están (`PA-T12`) |

Ningún objeto paró en el peldaño 4 tocando un invariante registrado: la escalera no se rompe. Ninguna regla de `CLAUDE.md` estorba; la regla 2 obliga a llevar la fecha como cadena, y así se diseña.

## Cómo se lee una hoja de APU

### Rótulos

`rotulo_normalizado(texto)` es `_normalizar_rotulo(texto).rstrip(":")`: sin espacios en los extremos ni en el interior, sin acentos, en minúsculas, sin puntos y sin dos puntos al final. Así `MATERIAL:`, `"MATERIAL "` (con espacio final) y `Material` dan `material`; `P.U:` da `pu`; `IVA 16% MATERIALES` da `iva16%materiales`.

| Rótulo normalizado en la columna A | Efecto |
|---|---|
| `material` | Abre el bloque `MATERIAL`. Su primera aparición marca el inicio del análisis |
| `manodeobra` | Abre el bloque `MANO_OBRA` |
| `costodirecto` | Cierra los insumos y abre la zona de cargos |
| empieza por `viaticos` | Abre el bloque de viáticos |
| `preciounitario` | Pie. Su primera aparición después de `material` cierra el análisis |
| empieza por `subtotal`, `total` o `suma` | Fila de subtotal: se ignora sin hallazgo en cualquier bloque `(asumido, P9)` |

`tipo_de_cargo(rotulo)` devuelve el tipo por el rótulo normalizado: `herramientamenor` → `HERRAMIENTA_MENOR`, `andamiaje` → `ANDAMIAJE`, `desperdicio` → `DESPERDICIO`, `indirectos` → `INDIRECTOS`, `utilidad` → `UTILIDAD` (igualdad exacta), y todo lo que **empieza por** `iva` → `IVA` (`PA-T7`). Cualquier otro, incluido `siroc`, devuelve `None`. `VIATICOS` no se asigna por rótulo: lo da el bloque.

### Reconocimiento (`M1`)

Una hoja es de APU si y solo si su columna A tiene una fila con rótulo `material` y, después de ella, una con `preciounitario`. Si no, `analizar_hoja_apu` devuelve `None` y no hay hallazgo (`RESUMEN US F2`, `BORRADOR DE GENERADORES`, `REFUERZOS`). El adaptador salta además la hoja que `elegir_hoja` eligió como catálogo, para no recorrer sus miles de filas.

### Cabecera (`M2`)

Se buscan los rótulos en **cualquier columna** de las filas anteriores a la fila `material`, y cuenta la primera aparición de cada uno en orden de fila y de columna. El valor está en **la columna constante del campo y la fila del rótulo**:

| Campo | Rótulos normalizados | Columna del valor | Origen |
|---|---|---|---|
| `codigo` | `codigo` | `C` | Spec, `CA-7` (fila 12, columna C) |
| `precio_unitario` (de la cabecera) | `pu` | `C` | Spec, `CA-9` (fila 15, columna C) |
| `unidad` | `unidad` | la que mida E-1 | `(sin ejecutar, E-1)` |
| `fecha` | `fecha` | la que mida E-1 | `(sin ejecutar, E-1)` |
| `analista` | `analista` | la que mida E-1 | `(sin ejecutar, E-1)` |

Si E-1 encuentra un literal de rótulo distinto (por ejemplo `elaboro`), se añade al conjunto de su campo y se anota en `impl.md`. Si un campo cae en columnas distintas entre hojas, o su rótulo aparece dos veces en una cabecera, **la fila A0 se detiene y se escala**. El rótulo `CONCEPTO` no se lee: ningún Must lo pide, y su `#REF!` en las 20 hojas de Union sería ruido.

| Campo | Lectura | Hallazgos |
|---|---|---|
| `codigo` | `normalizar_codigo(valor)` | Rótulo ausente: `fila_codigo=None`, sin hallazgo de lectura (lo reporta la asociación). Vacío: `None`, sin hallazgo de lectura. Literal de error: `None` y `ERROR_DE_FORMULA` en `(fila, "C")` |
| `unidad` | Como el catálogo: `normalizar_unidad`; si no la reconoce, el texto original | Vacía o rótulo ausente: `VALOR_AUSENTE`. Error: `ERROR_DE_FORMULA` y `None`. No reconocida: `UNIDAD_NO_RECONOCIDA` con el original |
| `fecha` | `interpretar_fecha(valor)` | La causa que devuelva, en la celda del valor |
| `analista` | Cadena recortada; si no es cadena, `_como_texto` | Vacía o rótulo ausente: `VALOR_AUSENTE`. Error: `ERROR_DE_FORMULA` y `None` (`PA-T9`) |
| `precio_unitario` | `_interpretar_no_negativo(valor, Dinero)`; informativo, no se compara (`PA-T5`) | La causa que devuelva (`CA-9`: `ERROR_DE_FORMULA`, fila 15, columna C, `#REF!`) |

Con el rótulo ausente, el hallazgo lleva `fila=None`, `columna=None`, `valor_original=None` y `detalle="sin rótulo «<campo>» en la cabecera"`.

`interpretar_fecha(valor: ValorCelda) -> str | CausaHallazgo`: `None` o cadena en blanco → `VALOR_AUSENTE`; cadena cuyo `strip()` está en `ERRORES_DE_FORMULA` → `ERROR_DE_FORMULA`; cadena cuyo `strip()` cumple `^(\d{4}-\d{2}-\d{2})(?: 00:00:00)?$` → el grupo 1; cualquier otra cadena, `int` o `Decimal` → `FECHA_NO_RECONOCIDA`. La forma `AAAA-MM-DD 00:00:00` es la que produce `_a_valor_celda` con `str(datetime)` cuando openpyxl entrega una fecha `(sin ejecutar, E-6)`. No valida el calendario: openpyxl construyó la fecha, así que es válida; una cadena tecleada a mano no pasa la expresión.

### Bloques (`M3`, `M4`)

Se recorren las filas estrictamente entre la fila `material` y la del pie. Para cada una:

1. Si la columna A no tiene texto (vacía o no cadena), se salta.
2. Si su rótulo abre un bloque, cambia el bloque y se salta la fila.
3. Si empieza por un prefijo de subtotal, se salta.
4. Si `E`, `F` y `G` están las tres vacías (`_celda_vacia`), la fila no tiene cifras. En el bloque de viáticos, una fila sin cifras **cierra el bloque** (pasa a la zona de cargos) y se salta; en los demás, se salta sin hallazgo. Así se ignoran las filas extra `SACO`, `KG` o `ML` y los encabezados de columnas `(asumido, P9)`.
5. Según el bloque:

| Bloque | La fila con cifras es | Columnas |
|---|---|---|
| `MATERIAL` | `InsumoLeido` de tipo `MATERIAL` | descripción `A`, unidad `D`, costo `E`, rendimiento `F`, cargo `G` |
| `MANO_OBRA` | `InsumoLeido` de tipo `MANO_OBRA` (`PA-T8`) | las mismas |
| zona de cargos | `CargoLeido` con `tipo_de_cargo(rótulo)`. Si es `None`: hallazgo `CARGO_DESCONOCIDO` en `(fila, "A")` con el texto de A tal cual (`CA-6`) | rótulo `A`, base `E`, porcentaje `F`, importe `G` `(sin ejecutar, E-1)` |
| viáticos | Si `tipo_de_cargo(rótulo)` no es `None`, la fila cierra el bloque y se lee como cargo de ese tipo en la zona de cargos. Si no, `CargoLeido` de tipo `VIATICOS` cuyo rótulo es el rol (`OFICIAL TABLAROQUERO`) | las de la zona de cargos |

Las columnas de base y porcentaje son la hipótesis de este diseño (base en `E` y porcentaje en `F`, como costo y rendimiento en los insumos); E-1 las confirma. Si E-1 da otras letras iguales en las 44 hojas, se usan las medidas y se anota en `impl.md`; si difieren entre hojas, **se escala antes de A1**.

**Datos de un insumo.** `descripcion` es el texto de A recortado; `clave` es `normalizar_clave_insumo(descripcion)`. La unidad se lee como en la cabecera, en la columna `D` (`CA-13`). Costo con `_interpretar_no_negativo(…, Dinero)`, rendimiento con `_interpretar_no_negativo(…, Rendimiento)`, cargo con `_interpretar_no_negativo(…, Dinero)`. Cada causa da `Hallazgo(causa, hoja, fila, <letra>, _texto_original(valor))` y el campo queda `None`, **nunca cero** (`CA-11`). Rendimiento vacío da `VALOR_AUSENTE` en `F`.

**Datos de un cargo.** `rotulo` es el texto de A recortado. Base y importe con `_interpretar_no_negativo(…, Dinero)`, porcentaje con `_interpretar_no_negativo(…, Porcentaje)`. Una celda vacía da `VALOR_AUSENTE`, porque las tres columnas de `apu_cargo` son `NOT NULL` `(asumido, P13)`.

`_interpretar_no_negativo[N](valor, tipo) -> N | CausaHallazgo` llama a `interpretar_numero` y, si el resultado es un número con `.valor < 0`, devuelve `VALOR_NEGATIVO` (`M8`; las columnas de `apu`, `apu_insumo` y `apu_cargo` tienen `CHECK (… >= 0)`). No se toca `interpretar_numero` para esto: cambiaría el catálogo.

**Pie.** El valor del pie está en `G` de la fila `preciounitario`, leído con `_interpretar_no_negativo(…, Dinero)`. Es el P.U. del archivo contra el que se verifica (`PA-T5`).

### Totales y cuadre (`M7`, `S1`)

`totalizar_analisis(insumos, cargos) -> TotalesAnalisis`:

- `material`: `sumar(cargos de los insumos MATERIAL, Dinero)`, o `None` si alguno es `None`. Sin insumos, `Dinero(0)`.
- `mano_obra`: igual con `MANO_OBRA`.
- `costo_directo`: `material + mano_obra`, o `None` si falta uno.
- `cargos`: `sumar(importes de todos los cargos, Dinero)`, **incluidos los de tipo `None`** (`CA-6`), o `None` si alguno falta.
- `precio_unitario`: `costo_directo + cargos`, o `None` si falta uno.

Nada se cuantiza: todo se suma con el contexto exacto de `tipos_base` (`CA-16`).

`verificar_precio_unitario(hoja: str, fila_pie: int, archivo: Dinero | None, original_pie: str | None, totales: TotalesAnalisis, filas_ilegibles: Sequence[int]) -> Hallazgo | None`:

1. Si `archivo` o `totales.precio_unitario` es `None`: `Hallazgo(PU_NO_VERIFICABLE, hoja, fila_pie, "G", original_pie, detalle="valores ilegibles en las filas: " + filas unidas por ", ")`. `filas_ilegibles` son, en orden, las de los insumos sin cargo, los cargos sin importe y el pie si no se leyó. Nunca se da por cuadrado (`CA-11`).
2. Si no, `diferencia = totales.precio_unitario - archivo` (exacta). Si `abs(diferencia.valor) <= _TOLERANCIA_PU`, con `_TOLERANCIA_PU = Decimal("0.01")`, devuelve `None`.
3. Si no: `Hallazgo(PU_NO_CUADRA, hoja, fila_pie, "G", original_pie, detalle=f"archivo {format(archivo.valor, 'f')}; reconstruido {format(totales.precio_unitario.valor, 'f')}; diferencia {format(diferencia.valor, 'f')}")`. Ni el P.U. del archivo ni el reconstruido se corrigen.

La diferencia de exactamente `0.01` cuadra y la de `0.0100001` no, en los dos sentidos (`CA-10`). La comparación nunca pasa por `cuantizar()`: si lo hiciera, `0.0100001` quedaría en `0.0100` y cuadraría.

## Capas afectadas

### Dominio

| Archivo | Qué | Regla | Ticket |
|---|---|---|---|
| `backend/cimenta/presupuesto/dominio/analisis.py` | Objetos de valor del análisis y del libro (detalle abajo) | HDU-001 esc. 5, 6, 7, 9 y 10; invariante 27; regla 1 | a y b |
| `backend/cimenta/presupuesto/dominio/catalogo.py` | Diez miembros nuevos de `CausaHallazgo` | HDU-001 esc. 6, 7, 9 y 10 | a y b |
| `backend/cimenta/presupuesto/dominio/lectura_catalogo.py` | Restricción de `interpretar_numero` ampliada a `Rendimiento` y `Porcentaje` (una línea y el import) | `M3`, `M4` | a |
| `backend/cimenta/presupuesto/dominio/lectura_analisis.py` | Normalizaciones, máquina de estados, cabecera, insumos, cargos, totales y cuadre | HDU-001 esc. 5 y 6; `PA-T4` a `PA-T10` | a |
| `backend/cimenta/presupuesto/dominio/asociacion_analisis.py` | Asociación por código, códigos sin análisis, insumos por crear y composición del resultado | HDU-001 esc. 5, 7, 9 y 10 | b |

Todos con `from __future__ import annotations`, solo biblioteca estándar (`dataclasses`, `decimal`, `enum`, `re`, `collections.abc`) y `tipos_base`. Ninguno lleva una `RN-xx`: el docstring cita el escenario de HDU-001 y la `PA` que implementa.

#### `analisis.py`

```python
class TipoInsumo(StrEnum):   # MATERIAL, MANO_OBRA                                      (a)
class TipoCargo(StrEnum):    # HERRAMIENTA_MENOR, ANDAMIAJE, DESPERDICIO, VIATICOS,
                             # IVA, INDIRECTOS, UTILIDAD                                 (a)

@dataclass(frozen=True, slots=True)
class CabeceraLeida:                                                                    # (a)
    fila_codigo: int | None        # fila del rótulo «código»; None si no aparece
    codigo: str | None             # normalizado; None si vacío o ilegible
    unidad: str | None             # normalizada, o el original si no se reconoce
    fecha: str | None              # AAAA-MM-DD
    analista: str | None
    precio_unitario: Dinero | None # el de la cabecera, informativo (PA-T5)

@dataclass(frozen=True, slots=True)
class InsumoLeido:                                                                      # (a)
    fila: int
    tipo: TipoInsumo
    descripcion: str               # recortada
    clave: str                     # normalizar_clave_insumo(descripcion)
    unidad: str | None
    costo_unitario: Dinero | None
    rendimiento: Rendimiento | None
    cargo: Dinero | None

@dataclass(frozen=True, slots=True)
class CargoLeido:                                                                       # (a)
    fila: int
    rotulo: str                    # recortado; en viáticos, el rol
    tipo: TipoCargo | None         # None = desconocido (SIROC)
    porcentaje: Porcentaje | None
    base: Dinero | None
    importe: Dinero | None

@dataclass(frozen=True, slots=True)
class TotalesAnalisis:                                                                  # (a)
    material: Dinero | None        # None = «no calculable», nunca cero
    mano_obra: Dinero | None
    costo_directo: Dinero | None
    cargos: Dinero | None
    precio_unitario: Dinero | None # reconstruido

@dataclass(frozen=True, slots=True)
class AnalisisLeido:                                                                    # (a)
    hoja: str                      # tal como viene, con espacios finales
    cabecera: CabeceraLeida
    insumos: tuple[InsumoLeido, ...]
    cargos: tuple[CargoLeido, ...]
    fila_precio_unitario: int
    precio_unitario: Dinero | None # el del pie
    totales: TotalesAnalisis
    hallazgos: tuple[Hallazgo, ...]

@dataclass(frozen=True, slots=True)
class InsumoPorCrear:                                                                   # (b)
    clave: str
    descripcion: str               # la de la primera aparición, recortada
    unidad: str                    # una de UNIDADES_ADMITIDAS
    tipo: TipoInsumo
    creado_en_importacion: bool = True

@dataclass(frozen=True, slots=True)
class AsociacionLeida:                                                                  # (b)
    hoja: str
    codigo: str
    filas_catalogo: tuple[int, ...]  # ConceptoLeido.fila con ese código, en orden

@dataclass(frozen=True, slots=True)
class AnalisisDelLibro:                                                                 # (b)
    catalogo: CatalogoLeido
    analisis: tuple[AnalisisLeido, ...]          # en el orden de las hojas
    asociaciones: tuple[AsociacionLeida, ...]
    codigos_sin_analisis: tuple[str, ...]        # sin hallazgo: SIN_APU es de TKT-015
    insumos_por_crear: tuple[InsumoPorCrear, ...]
    hallazgos: tuple[Hallazgo, ...]              # de asociación y de insumos
```

#### Causas nuevas de `CausaHallazgo`

| Causa | Cuándo | Ticket |
|---|---|---|
| `VALOR_NEGATIVO` | Número negativo en costo, rendimiento, cargo, porcentaje, base, importe o P.U. | a |
| `FECHA_NO_RECONOCIDA` | La fecha de la cabecera no tiene la forma `AAAA-MM-DD` | a |
| `CARGO_DESCONOCIDO` | Cargo cuyo rótulo no tiene tipo (`CA-6`) | a |
| `PU_NO_CUADRA` | Diferencia mayor que 0.01 (`CA-10`); bloqueante por definición, y TKT-015 la clasifica | a |
| `PU_NO_VERIFICABLE` | Falta un valor para reconstruir o el pie (`CA-11`) | a |
| `ANALISIS_SIN_CODIGO` | Código vacío, ilegible o sin rótulo (`CA-7`) | b |
| `CODIGO_EN_VARIAS_HOJAS` | El mismo código en más de una hoja (`CA-8`) | b |
| `CODIGO_SIN_CONCEPTO` | Código único que no está en el catálogo (P5) | b |
| `UNIDAD_EN_CONFLICTO` | Una clave con dos unidades, o con una distinta de la existente (`CA-14`) | b |
| `TIPO_EN_CONFLICTO` | Una clave en el bloque de material y en el de mano de obra (P6) | b |

Como en TKT-013, ninguna repite un nombre de `importacion_error.tipo`: son hallazgos crudos que traduce TKT-015.

#### `lectura_analisis.py` (a)

| Firma | Qué hace |
|---|---|
| `normalizar_clave_insumo(descripcion: str) -> str` | `" ".join(descripcion.split()).upper()`: recorta, colapsa cualquier espacio interior (incluidos tabulador y espacio duro) y pasa a mayúsculas. No quita acentos ni puntos (decisión 1) |
| `normalizar_codigo(valor: ValorCelda) -> str \| None` | `None` si `_celda_vacia(valor)`; si no, `_como_texto(valor).upper()` (`PA-T4`). Vale para la celda de la hoja y para `ConceptoLeido.codigo` |
| `rotulo_normalizado(texto: str) -> str` | `_normalizar_rotulo(texto).rstrip(":")` |
| `tipo_de_cargo(rotulo: str) -> TipoCargo \| None` | Tabla de «Rótulos», sobre `rotulo_normalizado(rotulo)` |
| `interpretar_fecha(valor: ValorCelda) -> str \| CausaHallazgo` | Ver «Cabecera» |
| `analizar_hoja_apu(hoja: str, filas: Iterable[tuple[int, tuple[ValorCelda, ...]]]) -> AnalisisLeido \| None` | Consume el iterable una vez. `None` si la hoja no es de APU. Hallazgos en orden de fila y, dentro de la fila, de columna; el del cuadre, al final |
| `totalizar_analisis(insumos: Sequence[InsumoLeido], cargos: Sequence[CargoLeido]) -> TotalesAnalisis` | `S1`; ver «Totales y cuadre» |
| `verificar_precio_unitario(...) -> Hallazgo \| None` | `M7`; ver «Totales y cuadre» |

Privados: `_interpretar_no_negativo`, `_Bloque` (`StrEnum` con `MATERIAL`, `MANO_OBRA`, `CARGOS`, `VIATICOS`), las constantes de columna (`_COL_DESCRIPCION = 0`, `_COL_UNIDAD = 3`, `_COL_COSTO = 4`, `_COL_RENDIMIENTO = 5`, `_COL_CARGO = 6`, `_COL_BASE = 4`, `_COL_PORCENTAJE = 5`, `_COL_IMPORTE = 6`, las de cabecera de E-1), `_PREFIJOS_DE_SUBTOTAL = ("subtotal", "total", "suma")` y `_TOLERANCIA_PU = Decimal("0.01")`.

#### `asociacion_analisis.py` (b)

| Firma | Qué hace |
|---|---|
| `asociar_analisis(analisis: Sequence[AnalisisLeido], catalogo: CatalogoLeido) -> tuple[tuple[AsociacionLeida, ...], tuple[str, ...], tuple[Hallazgo, ...]]` | Asociaciones, códigos del catálogo sin análisis y hallazgos |
| `proponer_insumos(analisis: Sequence[AnalisisLeido], insumos_existentes: Mapping[str, str]) -> tuple[tuple[InsumoPorCrear, ...], tuple[Hallazgo, ...]]` | Insumos por crear y hallazgos de conflicto |
| `consolidar_libro(catalogo: CatalogoLeido, analisis: Sequence[AnalisisLeido], insumos_existentes: Mapping[str, str]) -> AnalisisDelLibro` | Llama a las dos y arma el resultado; hallazgos de asociación primero |

**`asociar_analisis`, en este orden:**

1. Índice del catálogo: `normalizar_codigo(concepto.codigo)` → filas de los conceptos, en orden.
2. Cuenta de hojas por código normalizado de los análisis que lo tienen.
3. Por cada análisis, en orden de hoja:
   - `cabecera.codigo is None` → `Hallazgo(ANALISIS_SIN_CODIGO, hoja, cabecera.fila_codigo, "C" si hay fila y si no None, None, detalle="sin rótulo «código»" solo si no hay fila)`. No se asocia por nombre de hoja ni por descripción (`CA-7`).
   - Código en más de una hoja → `Hallazgo(CODIGO_EN_VARIAS_HOJAS, hoja, fila_codigo, "C", codigo, detalle=<las otras hojas, en orden, unidas por ", ">)`. **Ninguna de las hojas se asocia** `(P4)`.
   - Código único presente en el índice → `AsociacionLeida(hoja, codigo, filas)` (`CA-5`: 162 filas para `620001`).
   - Código único ausente del índice → `Hallazgo(CODIGO_SIN_CONCEPTO, hoja, fila_codigo, "C", codigo)` `(P5)`.
4. `codigos_sin_analisis`: los códigos del índice, en orden de primera aparición en el catálogo, que no tiene ningún análisis (los ambiguos sí lo tienen). Sin hallazgo.

**`proponer_insumos`.** `insumos_existentes` es `clave → unidad`, con las claves **ya normalizadas** con `normalizar_clave_insumo` por quien arma el mapa (TKT-017 o TKT-018) `(P12)`. El lector no consulta la base.

1. Ocurrencias: los insumos de todos los análisis, en orden de hoja y fila, cuya `unidad` esté en `UNIDADES_ADMITIDAS`. Los que no, ya tienen su hallazgo de lectura y no se proponen (`CA-13`).
2. Por cada clave, en orden de primera aparición:
   - Si está en `insumos_existentes`: por cada ocurrencia con unidad distinta, `Hallazgo(UNIDAD_EN_CONFLICTO, hoja, fila, "D", unidad, detalle=f"{clave}: existente {unidad_existente}")`. No se propone (`CA-14`).
   - Si tiene más de una unidad: por cada ocurrencia, `Hallazgo(UNIDAD_EN_CONFLICTO, hoja, fila, "D", unidad, detalle=f"{clave}: " + "; ".join(f"{hoja} fila {fila} {unidad}" de todas las ocurrencias))`. No se propone.
   - Si tiene más de un tipo: lo mismo con `TIPO_EN_CONFLICTO`, columna `"A"` y `valor_original` igual al tipo `(P6)`. No se propone.
   - Si no: `InsumoPorCrear(clave, descripcion de la primera ocurrencia, unidad, tipo)`, una sola vez (`CA-12`).

### Infraestructura

| Objeto | Tipo | Detalle |
|---|---|---|
| `backend/cimenta/presupuesto/infraestructura/lector_catalogo.py` | adaptador | Refactor sin cambio de comportamiento y `leer_libro_presupuesto`. Sigue siendo el único archivo que importa openpyxl; su docstring lo dice |

**Migración:** ninguna.

Cambios, en este orden (b):

1. Se extrae `_filas(hoja: ReadOnlyWorksheet) -> Iterator[tuple[int, tuple[ValorCelda, ...]]]`: llama a `hoja.reset_dimensions()` y devuelve el generador `enumerate(hoja.iter_rows(values_only=True), start=1)` con `_a_valor_celda`, idéntico al actual.
2. Se extrae `_leer_catalogo_de_libro(libro: Workbook) -> CatalogoLeido`: el contenido actual del bloque `try` (de `elegir_hoja` a `analizar_hoja`), usando `_filas`.
3. `leer_catalogo(contenido: bytes) -> CatalogoLeido` queda: `load_workbook` con el mismo `except`, y `try: return _leer_catalogo_de_libro(libro) finally: libro.close()`.
4. Nueva `leer_libro_presupuesto(contenido: bytes, insumos_existentes: Mapping[str, str]) -> AnalisisDelLibro`:
   - `load_workbook(BytesIO(contenido), read_only=True, data_only=True)`; ante `BadZipFile`, `InvalidFileException` o `KeyError`, devuelve `AnalisisDelLibro(catalogo=<el mismo catalogo_sin_conceptos que leer_catalogo>, analisis=(), asociaciones=(), codigos_sin_analisis=(), insumos_por_crear=(), hallazgos=())`.
   - En `try`/`finally` con `libro.close()`: `catalogo = _leer_catalogo_de_libro(libro)`; por cada `nombre` de `libro.sheetnames`, en orden, salta `nombre == catalogo.hoja` y las hojas que no sean `ReadOnlyWorksheet`; `resultado = analizar_hoja_apu(nombre, _filas(libro[nombre]))`; conserva los que no sean `None`. Devuelve `consolidar_libro(catalogo, analisis, insumos_existentes)`.

`Workbook` se importa de `openpyxl.workbook.workbook` `(sin ejecutar, E-10)`. El `ValueError` de defusedxml ante una entidad externa sigue saliendo como hoy (`test_tkt013_defusedxml_activo_y_rechaza_entidades_externas`).

### Sin API, aplicación ni frontend

Ninguna operación del borrador OpenAPI lleva TKT-014 en `x-tickets`. El caso de uso y las rutas son de TKT-018.

## Experimentos previos

Ninguno se ejecutó al diseñar: esta sesión no tiene intérprete. Las cifras de la spec las midió la persona dueña el 2026-11-02 con una normalización que el lector todavía no tiene. Los experimentos los ejecuta la fila A0 con un guion en el directorio temporal de la sesión, **nunca en el repositorio**, con `uv run python <guion>` desde `backend/` (openpyxl ya es dependencia) y las variables `CIMENTA_CATALOGO_ENITI` y `CIMENTA_CATALOGO_UNION`. La salida se pega en `impl.md` **sin descripciones de insumo ni precios del cliente** más allá de los que ya cita la spec; los rótulos de bloque y de cargo sí se pegan.

| # | Afirmación | Experimento | Resultado esperado | Fuente |
|---|---|---|---|---|
| E-1 | Disposición de una hoja: rótulos de bloque y de cargo en A; insumos con unidad en D, costo en E, rendimiento en F y cargo en G; cargos con base en E, porcentaje en F e importe en G; pie en G; cabecera con código y P.U. en C y la columna de unidad, fecha y analista | Volcar letra, tipo de Python y valor de cada celda no vacía de las filas 1 a 65 de `"MURO STD-635-STD "`, `01` y `14`, solo rótulos y cifras que cita la spec. Después, sobre las 44 hojas, la columna del valor de cada rótulo de cabecera | Lo de la columna de la izquierda; una sola columna por campo en las 44 hojas | `(sin ejecutar)`. **Si un campo varía de columna, o base y porcentaje no están en E y F en todas, se escala antes de A1** |
| E-2 | La tabla de rótulos clasifica todas las filas | Sobre las 44 hojas, el conjunto de rótulos normalizados de la columna A por bloque, con su cuenta y si `E`, `F` o `G` tienen cifra. Contar `material` y `preciounitario` por hoja | Una aparición de cada uno por hoja; ningún rótulo con cifras fuera de la tabla salvo insumos, roles de viáticos y `siroc`; las filas `SACO`, `KG` y `ML` sin cifras | `(sin ejecutar)`. **Si aparece un rótulo con cifras en la zona de cargos que no esté en la tabla y no sea `siroc`, se escala antes de A1** |
| E-3 | `RESUMEN US F2`, `BORRADOR DE GENERADORES` y `REFUERZOS` no tienen `material` y `preciounitario` en A | Aplicar el reconocimiento a todas las hojas de los dos libros | 24 en ENITI y 20 en Union | `(sin ejecutar)`. **Si sale otra cuenta, se escala antes de A1** |
| E-4 | Las cifras de la spec se cumplen con las reglas de este diseño | Prototipo en el guion: hojas sin código (21), códigos en dos hojas (`620014`, `620045`, `620050`), `#REF!` en `P.U:` (hojas `14`, `15`, `16`, `18`, `19`), `SIROC` (20 hojas), códigos distintos de ENITI (20), códigos del catálogo sin hoja (16), filas de `620001` (162), insumos distintos con `normalizar_clave_insumo` (29, 23, unión 35, comunes 17) y su reparto por tipo (26 y 3; 21 y 2). Además: claves con dos unidades y claves en los dos bloques, en cada libro | Las cifras de la spec; ninguna clave con dos unidades ni con dos tipos | Medición de la persona dueña del 2026-11-02 `(sin ejecutar con estas reglas)`. **Si hay conflictos de unidad o de tipo en los reales, las cuentas de `CA-12` cambian: se escala antes de B3** |
| E-5 | El cuadre de las 44 hojas y las cifras exactas de `"MURO STD-635-STD "` | Totales con `Decimal(repr(f))` y suma exacta: material, mano de obra, costo directo, cargos, P.U. reconstruido y diferencia con el pie, por hoja; la diferencia máxima | Diferencia máxima muy por debajo de 0.01. Los totales exactos de `"MURO STD-635-STD "` se anotan: son los literales de TC-42 | `(sin ejecutar)`. Si la suma exacta difiere de las cifras de `CA-3` y `CA-16` (que vienen de `float`), aplica P3 |
| E-6 | openpyxl entrega la fecha de la cabecera como `datetime` y `str()` da `AAAA-MM-DD 00:00:00` | Tipo y `str` de la celda de fecha de `01` y de `"MURO STD-635-STD "` | `datetime`; `'2026-08-25 00:00:00'` y `'2025-09-01 00:00:00'` | Documentación de openpyxl: las fechas se convierten a `datetime` (Context7) `(sin ejecutar)`. **Si llega como texto o número, se escala antes de A1** |
| E-7 | `str.split()` sin argumento corta en tabulador y en espacio duro (`\xa0`) | `"A\t B\xa0 C".split()` | `['A', 'B', 'C']` | Biblioteca estándar `(sin ejecutar)` |
| E-8 | En un libro de solo lectura se recorren varias hojas, una tras otra, en la misma apertura | Recorrer con `iter_rows` la hoja del catálogo y después cada hoja de APU en una sola apertura; tiempo total frente a dos aperturas | Las filas de cada hoja completas; una apertura más rápida que dos | Documentación «Read-only mode» (Context7) `(sin ejecutar)`. El tiempo se anota para TKT-015 |
| E-9 | `pickle` conserva `AnalisisDelLibro` | `pickle.loads(pickle.dumps(r)) == r` sobre ENITI | Igualdad | `(sin ejecutar)`. Informativo para TKT-015 |
| E-10 | `Workbook` se importa de `openpyxl.workbook.workbook` y mypy lo acepta con `types-openpyxl` | Módulo de prueba en el directorio temporal | mypy sin errores | `(sin ejecutar)`. Lo corre B3 |

## Orden de implementación

Se ejecuta fila por fila con el ciclo TDD de [metodología §16](../../metodologia.md#16--el-ciclo-tdd): rojo, verde, refactor. La verificación de cada paso corre **antes** de pasar al siguiente. Todas las órdenes, desde `backend/`.

### Entrega TKT-014a · dominio de la hoja

| # | Paso | Tests que pone en verde | Agente | Modelo | Verificación | Estado |
|---|---|---|---|---|---|---|
| A0 | Experimentos E-1 a E-7 con un guion en el directorio temporal; salida en `impl.md`. Fija en `impl.md` las letras de unidad, fecha y analista, los literales de rótulo medidos y los totales exactos de E-5. Sin código del repositorio | — | `tester-backend` | `haiku` · tarea mecánica: el guion y lo esperado están escritos aquí | Cada resultado coincide con «Resultado esperado». **Si E-1, E-2, E-3 o E-6 no coinciden, `/sdd-escalar` antes de A1** | Pendiente |
| A1 | `analisis.py` (parte a), las cinco causas de a, la restricción de `interpretar_numero`, y en `lectura_analisis.py`: `normalizar_clave_insumo`, `normalizar_codigo`, `rotulo_normalizado`, `tipo_de_cargo`, `interpretar_fecha`. El tester escribe además `herramientas/soporte_tkt014.py` con la hoja sintética. ~120 líneas | TC-01 a TC-06 | `desarrollador-dominio` | `haiku` | `uv run pytest tests/test_tkt014_hoja.py -k "clave or codigo or rotulo or numero or fecha"`; `uv run python -m herramientas.verificar_float`; `uv run pytest tests/test_tkt013_dominio.py` | Pendiente |
| A2 | `analizar_hoja_apu`: reconocimiento, cabecera y esqueleto de bloques, con `totales` y cuadre provisionales en `None` hasta A4. ~90 líneas | TC-07, TC-19, TC-22 | `desarrollador-dominio` | `haiku` | `uv run pytest tests/test_tkt014_hoja.py -k "estructura or cabecera or codigo_de_cabecera"` | Pendiente |
| A3 | Bloques: insumos, cargos, viáticos, subtotales, filas sin cifras, `_interpretar_no_negativo`. ~100 líneas | TC-09, TC-10, TC-11, TC-14, TC-18, TC-21 | `desarrollador-dominio` | `haiku` | `uv run pytest tests/test_tkt014_hoja.py -k "bloque or viaticos or subtotal or ilegibles or unidad or inmutable"` | Pendiente |
| A4 | `totalizar_analisis`, `verificar_precio_unitario` y su llamada al final de `analizar_hoja_apu`. ~60 líneas | TC-08, TC-12, TC-13, TC-15, TC-16, TC-17, TC-20 | `desarrollador-dominio` | `sonnet` · disparador: regla de dinero con frontera (tolerancia ±0.01 inclusive, decisión 4 de la persona dueña), afín a `RN-03` | `uv run pytest tests/test_tkt014_hoja.py` completo en verde | Pendiente |
| A5 | Cierre de a: mutantes M-01 a M-13; ficha de TKT-014 en `docs/05` con la partición; suite completa | Todos los de a, TC-INV-1, TC-INV-2 y la suite de TKT-013 | `tester-backend` | `sonnet` · valor por omisión del agente: la mutación es el oráculo del oráculo | Cada mutante aplicado, test en rojo, revertido, salida en `impl.md`; `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .`, `uv run lint-imports`, `uv run python -m herramientas.verificar_float`, `uv run pytest`; `python tools/verificar_docs.py` | Pendiente |

### Entrega TKT-014b · asociación, insumos, adaptador y archivos reales

| # | Paso | Tests que pone en verde | Agente | Modelo | Verificación | Estado |
|---|---|---|---|---|---|---|
| B1 | `AsociacionLeida`, las causas `ANALISIS_SIN_CODIGO`, `CODIGO_EN_VARIAS_HOJAS` y `CODIGO_SIN_CONCEPTO`, y `asociar_analisis`. ~60 líneas | TC-23 a TC-27 | `desarrollador-dominio` | `haiku` | `uv run pytest tests/test_tkt014_asociacion.py -k "asocia or codigo or sin_codigo"` | Pendiente |
| B2 | `InsumoPorCrear`, `AnalisisDelLibro`, las causas `UNIDAD_EN_CONFLICTO` y `TIPO_EN_CONFLICTO`, `proponer_insumos` y `consolidar_libro`. ~70 líneas | TC-28 a TC-33 | `desarrollador-dominio` | `haiku` | `uv run pytest tests/test_tkt014_asociacion.py` completo | Pendiente |
| B3 | Refactor de `lector_catalogo.py` (`_filas`, `_leer_catalogo_de_libro`) y `leer_libro_presupuesto`; E-8, E-9 y E-10. El tester amplía `soporte_tkt014.py` para escribir la hoja sintética en un `LibroCatalogo` (sin tocar `conftest.py`) y escribe las pruebas sintéticas y las de archivos reales. ~55 líneas de producción | TC-34 a TC-49, TC-INV-3 y TC-INV-4 | `desarrollador-aplicacion` (carga `conv-backend-fastapi`, que cubre `infraestructura/`) | `haiku` | `uv run pytest tests/test_tkt013_lector.py tests/test_tkt013_archivos_reales.py tests/test_tkt014_lector.py tests/test_tkt014_archivos_reales.py -ra`. Sin las variables, las de archivos reales salen `SKIPPED` con su motivo; **con las dos variables definidas, en verde**, y la salida en `impl.md` | Pendiente |
| B4 | Documentación de b y ADR-034 (ver «Documentación afectada»). Sin código | — | `desarrollador-dominio` | `haiku` | `python tools/verificar_docs.py`; `python -m unittest discover -s tools/tests -v`; `Grep` de «33 decisiones» sin resultados y salida en `impl.md` | Pendiente |
| B5 | Cierre de b: mutantes M-14 a M-18 y la suite completa con y sin las variables de entorno | Todos los de b y la regresión completa | `tester-backend` | `sonnet` · valor por omisión del agente | Cada mutante en rojo y revertido; el trabajo `backend` de `ci.yml` en verde en local | Pendiente |

**Modelo:** `haiku` por omisión. Solo A4 cae en un disparador de [metodología §14](../../metodologia.md#14--enrutamiento-de-modelo): es la única fila que decide si una cifra de dinero pasa o se bloquea, y su frontera es exacta. Las filas de cierre van en `sonnet` porque es el valor por omisión de `tester-backend`. Ninguna fila va en `opus`.

Estado: `Pendiente` · `✓ Hecho` · `⚠ Ajustado` (y el ajuste se documenta en `impl.md`).

## Plan de pruebas

Las pruebas del dominio construyen las filas como tuplas con `herramientas/soporte_tkt014.py` (fuera de `tests/` por el aprendizaje de TKT-013 con mypy): `hoja_apu_sintetica(**variantes) -> list[tuple[int, tuple[ValorCelda, ...]]]`, con código en la fila 12 columna C, P.U. de cabecera en la fila 15 columna C, la disposición de E-1 y **cifras neutras**:

| Fila | A | D | E | F | G |
|---|---|---|---|---|---|
| bloque | `MATERIAL` | | | | |
| insumo | `MATERIAL UNO` | `PZA` | `10` | `2` | `20` |
| insumo | `MATERIAL DOS` | `KG` | `5` | `1.5` | `7.5` |
| bloque | `MANO DE OBRA` | | | | |
| insumo | `CUADRILLA X` | `JORNAL` | `1000` | `10` | `100` |
| bloque | `COSTO DIRECTO` | | | | `127.5` |
| cargo | `HERRAMIENTA MENOR` | | `127.5` | `0.01` | `1.275` |
| bloque | `VIATICOS Y HOSPEDAJE` | | | | |
| cargo | `OFICIAL X` | | `0` | `0` | `0` |
| cargo | `INDIRECTOS` | | `128.775` | `0.08` | `10.302` |
| cargo | `UTILIDAD` | | `128.775` | `0.12` | `15.453` |
| cargo | `IVA` | | `27.5` | `0.16` | `4.4` |
| pie | `PRECIO UNITARIO` | | | | `158.93` |

El P.U. reconstruido es exactamente `158.93`. Las variantes (`siroc=True` añade `SIROC` al 1 % y sube el pie a `160.205`; `pie=…`; celdas rotas) se pasan por parámetro. Las pruebas con openpyxl escriben esa misma hoja en un `LibroCatalogo` junto con `libro_forma_eniti`. Las de archivos reales usan `archivo_eniti` y `archivo_union`, que se omiten con motivo si falta la variable. **Ningún dato del cliente entra al repositorio** salvo las cifras y nombres que ya cita la spec.

Todo rechazo comprueba el hallazgo completo (`causa`, `hoja`, `fila`, `columna`, `valor_original` y, donde aplica, `detalle`) **y** que el campo afectado quedó `None`, no en cero.

### TKT-014a · dominio de la hoja (`tests/test_tkt014_hoja.py`)

| # | Caso | Tipo | Criterio | Escenario |
|---|---|---|---|---|
| TC-01 | `test_hdu001_esc10_clave_de_insumo_normalizada`, parametrizada: `" canal  635x3.05 cal.26 "`, `"CANAL\t635X3.05\xa0CAL.26"` y `"CANAL 635X3.05 CAL.26"` → `"CANAL 635X3.05 CAL.26"` | feliz | `CA-12` | `HDU-001 esc. 10` |
| TC-02 | `test_hdu001_esc05_codigo_de_analisis_normalizado`: `620001` → `"620001"`; `Decimal("620001.0")` → `"620001"`; `" 620040-a "` → `"620040-A"`; `None` y `"  "` → `None` | feliz y borde | `CA-5` · `PA-T4` | `HDU-001 esc. 5` |
| TC-03 | `test_hdu001_esc05_rotulos_de_cargo_se_tipifican`, parametrizada: `HERRAMIENTA MENOR`, `Herramienta  Menor:`, `ANDAMIAJE`, `DESPERDICIO`, `INDIRECTOS`, `UTILIDAD`, `IVA`, ` iva `, `IVA 16% MATERIALES` → su tipo | feliz | `CA-4` · `PA-T7` | `HDU-001 esc. 5` |
| TC-04 | `test_hdu001_esc06_rotulo_ajeno_no_recibe_tipo`: `SIROC`, `INDIRECTO`, `OTROS CARGOS` → `None`; nunca `INDIRECTOS` | **rechazo** | `CA-6` | `HDU-001 esc. 6` |
| TC-05 | `test_hdu001_esc05_rendimiento_y_porcentaje_exactos`: `interpretar_numero(Decimal("0.3278"), Rendimiento) == Rendimiento("0.3278")` con `.valor` sin cuantizar; `Decimal("0.16")` → `Porcentaje("0.16")`; `"#REF!"` → `ERROR_DE_FORMULA` | feliz y **rechazo** | `CA-15` | `HDU-001 esc. 5` |
| TC-06 | `test_hdu001_esc06_fecha_de_la_cabecera`: `"2025-09-01 00:00:00"` → `"2025-09-01"`; `"01/09/2025"`, `"2025-09-01 10:30:00"` y `45901` → `FECHA_NO_RECONOCIDA`; `None` → `VALOR_AUSENTE`; `"#REF!"` → `ERROR_DE_FORMULA` | feliz y **rechazo** | `CA-3` · `PA-T9` | `HDU-001 esc. 6` |
| TC-07 | `test_hdu001_esc05_hoja_sin_estructura_de_apu_no_es_analisis`: filas sin `MATERIAL`; con `MATERIAL` y sin `PRECIO UNITARIO`; con `PRECIO UNITARIO` antes de `MATERIAL`; filas con la forma del catálogo → `None` | **rechazo** | `CA-2` · `M1` | `HDU-001 esc. 5` |
| TC-08 | `test_hdu001_esc05_analisis_sintetico_completo`: la hoja sintética → cabecera (`P-001`, `M2`, `2025-09-01`, analista, P.U.), dos materiales y una mano de obra con sus cifras y tipos, cinco cargos con tipo, porcentaje, base e importe, totales `27.5`, `100`, `127.5`, `31.43` y `158.93`, `hallazgos == ()` | feliz | `CA-1`, `CA-3`, `CA-4`, `CA-16` | `HDU-001 esc. 5` |
| TC-09 | `test_hdu001_esc05_variantes_de_rotulo_de_bloque`, parametrizada: `MATERIAL:`, `"MATERIAL "`, `Material`, `MANO DE OBRA:`; y una fila extra `("SACO",)` y otra con solo `KG` en D bajo el rótulo → mismos insumos y ningún hallazgo | feliz | `CA-1`, `CA-2` · `M1` | `HDU-001 esc. 5` |
| TC-10 | `test_hdu001_esc05_viaticos_por_rol_son_cargos_viaticos`: dos roles → dos cargos `VIATICOS` con el rol como rótulo, porcentaje `0` e importe `0`; `INDIRECTOS` tras ellos sale `INDIRECTOS` | feliz | `CA-4` · `PA-T7` | `HDU-001 esc. 5` |
| TC-11 | `test_hdu001_esc05_filas_de_subtotal_se_ignoran`: `SUBTOTAL` y `TOTAL MATERIAL` con cifra en G → no son insumos ni cargos; una fila sin A con cifra en G tampoco | borde | `M1` · P9 | `HDU-001 esc. 5` |
| TC-12 | `test_hdu001_esc06_cargo_desconocido_se_conserva_sin_tipo`: variante `siroc=True` → `CargoLeido(tipo=None, rotulo="SIROC", porcentaje=Porcentaje("0.01"), base=Dinero("127.5"), importe=Dinero("1.275"))`; `Hallazgo(CARGO_DESCONOCIDO, hoja, fila, "A", "SIROC")`; reconstruido `160.205` y sin hallazgo de cuadre | **rechazo** | `CA-6` | `HDU-001 esc. 6` |
| TC-13 | `test_hdu001_esc06_pu_de_cabecera_con_ref`: P.U. de cabecera `"#REF!"` → `Hallazgo(ERROR_DE_FORMULA, hoja, 15, "C", "#REF!")`; `cabecera.precio_unitario is None`; el pie es la referencia y no hay `PU_NO_VERIFICABLE` ni `PU_NO_CUADRA` | **rechazo** | `CA-9` · `PA-T5` | `HDU-001 esc. 6` |
| TC-14 | `test_hdu001_esc06_celdas_de_insumo_ilegibles`: rendimiento `"#REF!"` (`ERROR_DE_FORMULA`, F), costo `"veinte"` (`NO_ES_NUMERO`, E), rendimiento `-1` (`VALOR_NEGATIVO`, F, `"-1"`), rendimiento vacío (`VALOR_AUSENTE`, F) → cada campo `None` y los insumos conservados | **rechazo** | `CA-11` · `M8` | `HDU-001 esc. 6` |
| TC-15 | `test_hdu001_esc06_pu_no_verificable`: cargo de un insumo `"#REF!"` → `PU_NO_VERIFICABLE` en `(fila del pie, "G")` con `detalle` que nombra esa fila; `totales.material`, `costo_directo` y `precio_unitario` `None`; ningún `PU_NO_CUADRA`. Y con el pie `"#REF!"`: `ERROR_DE_FORMULA` y `PU_NO_VERIFICABLE` | **rechazo** | `CA-11`, `CA-16` | `HDU-001 esc. 6` |
| TC-16 | `test_hdu001_esc06_frontera_de_tolerancia`, parametrizada por el pie: `158.94` y `158.92` → sin hallazgo; `158.9400001` y `158.9199999` → `PU_NO_CUADRA` con hoja, fila del pie, `G`, `valor_original="158.9400001"` y `detalle` igual a la cadena de la regla armada con `format(…, "f")` de las tres cifras (la escala del reconstruido depende de los exponentes de los sumandos: `158.930`), con diferencia `-0.0100001` y `0.0100001` | **rechazo** y borde | `CA-10` | `HDU-001 esc. 6` |
| TC-17 | `test_hdu001_esc06_pu_que_no_cuadra_reporta_cifras`: `verificar_precio_unitario` con archivo `Dinero("641.38")` y reconstruido `641.3608310977561` → `detalle == "archivo 641.38; reconstruido 641.3608310977561; diferencia -0.0191689022439"`; el `AnalisisLeido` conserva `precio_unitario == Dinero("641.38")` (P2) | **rechazo** | `CA-10` | `HDU-001 esc. 6` |
| TC-18 | `test_hdu001_esc10_unidad_de_insumo_fuera_del_catalogo`: `LT` y `M²` → unidad original y `Hallazgo(UNIDAD_NO_RECONOCIDA, hoja, fila, "D", <original>)`; `"CAJA "` y `pza` → `CAJA` y `PZA` sin hallazgo | **rechazo** | `CA-13` · invariante 27 | `HDU-001 esc. 10` |
| TC-19 | `test_hdu001_esc06_cabecera_incompleta`: sin rótulo de fecha, analista vacío, unidad `LT` → `VALOR_AUSENTE` (con `detalle` del rótulo ausente), `VALOR_AUSENTE` y `UNIDAD_NO_RECONOCIDA`; el análisis se conserva | **rechazo** | `PA-T9` · `M2` | `HDU-001 esc. 6` |
| TC-20 | `test_hdu001_esc05_totales_con_precision_completa`: cargos `"14.613323999999999"` y `"0.000000000000001"` → material `14.613324000000000` exacto, sin cuantizar | borde | `CA-16` | `HDU-001 esc. 5` |
| TC-21 | `test_hdu001_esc05_resultado_inmutable_y_en_decimal`: asignar un atributo de `AnalisisLeido`, `InsumoLeido` y `CargoLeido` lanza `FrozenInstanceError`; las colecciones son `tuple`; todo `.valor` es `Decimal` | feliz | `CA-15` · `M9` | `HDU-001 esc. 5` |
| TC-22 | `test_hdu001_esc05_codigo_de_cabecera`: `620001` → `"620001"` y `fila_codigo == 12`; `"#REF!"` → `codigo is None` y `Hallazgo(ERROR_DE_FORMULA, hoja, 12, "C", "#REF!")`; vacío → `None` sin hallazgo de lectura | feliz y **rechazo** | `CA-5`, `CA-7` | `HDU-001 esc. 5` |
| TC-INV-1 | `lint-imports` en verde con los módulos nuevos | regresión | `CA-R1` | reglas 2 y 3 |
| TC-INV-2 | `verificar_float` en verde | regresión | `CA-R2` | regla 1 |

### TKT-014b · asociación e insumos (`tests/test_tkt014_asociacion.py`)

Construyen `CatalogoLeido` y `AnalisisLeido` en memoria con ayudantes de `soporte_tkt014.py`.

| # | Caso | Tipo | Criterio | Escenario |
|---|---|---|---|---|
| TC-23 | `test_hdu001_esc05_asocia_por_codigo`: catálogo con tres filas `P-001` (una escrita ` p-001 `) y una `P-040-A`; análisis con esos códigos → asociaciones con las filas en orden | feliz | `CA-5` | `HDU-001 esc. 5` |
| TC-24 | `test_hdu001_esc05_codigos_del_catalogo_sin_analisis`: lista en orden de primera aparición; ningún hallazgo por ellos | feliz | `CA-5` | `HDU-001 esc. 5` |
| TC-25 | `test_hdu001_esc07_analisis_sin_codigo`: código `None` con `fila_codigo=12` → `Hallazgo(ANALISIS_SIN_CODIGO, hoja, 12, "C", None)`; sin rótulo → `fila=None`, `columna=None`, `detalle="sin rótulo «código»"`; una hoja llamada como la descripción de un concepto no se asocia; el análisis sigue en `analisis` | **rechazo** | `CA-7` | `HDU-001 esc. 7` |
| TC-26 | `test_hdu001_esc09_codigo_en_dos_hojas`: dos hojas con `P-014` → dos hallazgos `CODIGO_EN_VARIAS_HOJAS` con `valor_original="P-014"` y `detalle` igual a la otra hoja; ninguna asociación; los dos análisis conservan su contenido | **rechazo** | `CA-8` | `HDU-001 esc. 9` |
| TC-27 | `test_hdu001_esc05_codigo_sin_concepto`: código único ausente del catálogo → `CODIGO_SIN_CONCEPTO` con hoja, fila 12, `C` y el código (P5) | **rechazo** | `M5` | `HDU-001 esc. 5` |
| TC-28 | `test_hdu001_esc10_insumos_por_crear_por_clave`: existentes `{"CANAL 635X3.05 CAL.26": "PZA"}`; ocurrencias `"canal 635x3.05  cal.26 "` y `"CANAL 635X3.05 CAL.26 "` no se proponen; otro insumo repetido en dos hojas aparece una vez con descripción recortada, unidad normalizada, tipo y `creado_en_importacion is True` | feliz | `CA-12` | `HDU-001 esc. 10` |
| TC-29 | `test_hdu001_esc10_unidad_fuera_del_catalogo_no_se_propone`: insumos con `LT` y `M²` no aparecen en `insumos_por_crear` | **rechazo** | `CA-13` | `HDU-001 esc. 10` |
| TC-30 | `test_hdu001_esc10_unidad_en_conflicto_entre_hojas`: `TORNILLO S-1` con `PZA` y `CAJA` → dos `UNIDAD_EN_CONFLICTO` (columna `D`, cada uno con su hoja, fila y unidad; `detalle` con las dos); no se propone | **rechazo** | `CA-14` | `HDU-001 esc. 10` |
| TC-31 | `test_hdu001_esc10_unidad_distinta_de_la_existente`: existente `PZA`, leído `CAJA` → `UNIDAD_EN_CONFLICTO` con `detalle="TORNILLO S-1: existente PZA"` | **rechazo** | `CA-14` | `HDU-001 esc. 10` |
| TC-32 | `test_hdu001_esc10_tipo_en_conflicto`: la misma clave en material y en mano de obra → `TIPO_EN_CONFLICTO`; no se propone (P6) | **rechazo** | `M6` | `HDU-001 esc. 10` |
| TC-33 | `test_hdu001_esc10_el_lector_no_consulta_la_base`: los parámetros de `proponer_insumos` y `consolidar_libro` son los de este diseño; ningún módulo nuevo importa `sqlalchemy` ni `psycopg` (por `ast`) | feliz | `CA-12`, `CA-15` | `HDU-001 esc. 10` |

### TKT-014b · adaptador (`tests/test_tkt014_lector.py`) y archivos reales (`tests/test_tkt014_archivos_reales.py`)

| # | Caso | Tipo | Criterio | Escenario |
|---|---|---|---|---|
| TC-34 | `test_hdu001_esc05_libro_sintetico_con_catalogo_y_apu`: `libro_forma_eniti` más dos hojas de APU (una llamada `"APU X "` con espacio final) y `RESUMEN` → `catalogo == leer_catalogo(contenido)`; dos análisis en orden de hoja; `RESUMEN` sin análisis ni hallazgo; nombre con espacio conservado | feliz | `CA-1`, `CA-2`, `CA-R3` | `HDU-001 esc. 5` |
| TC-35 | `test_hdu001_esc05_el_libro_se_abre_una_vez`: con `monkeypatch` sobre `load_workbook` del módulo y sobre `ReadOnlyWorksheet.iter_rows`, una llamada a `load_workbook` y cada hoja recorrida una sola vez | feliz | `CA-R3` | `HDU-001 esc. 5` |
| TC-36 | `test_hdu001_esc05_fecha_y_flotantes_del_libro`: celda `datetime(2025, 9, 1)` → `"2025-09-01"`; `0.3278` escrito como `float` → `Rendimiento("0.3278")` | feliz | `CA-15` | `HDU-001 esc. 5` |
| TC-37 | `test_hdu001_esc06_libro_sintetico_con_rechazos`: `SIROC`, `#REF!` en el P.U. de cabecera y las celdas rotas de TC-14 → los mismos hallazgos que en el dominio, con hoja, fila y columna del libro | **rechazo** | `CA-6`, `CA-9`, `CA-11` | `HDU-001 esc. 6` |
| TC-38 | `test_hdu001_esc05_leer_libro_no_escribe`: con el rol de aplicación, `apu`, `apu_insumo`, `apu_cargo` e `insumo` sin filas nuevas; dos lecturas iguales; todo `.valor` `Decimal` | feliz | `CA-15` | `HDU-001 esc. 5` |
| TC-39 | `test_hdu001_esc27_contenido_invalido_en_libro_presupuesto`: `b""` → hallazgo del catálogo igual al de `leer_catalogo` y `analisis == ()`, sin excepción | **rechazo** | `CA-15` | `HDU-001 esc. 27` |
| TC-40 | `test_hdu001_esc05_analisis_reales_de_eniti` (real): 24 en orden; ninguno de `CATALOGO`; el primero `01`, `620001`, `M2`, `2026-08-25`, P.U. `Dinero("668.6929342319413")` en cabecera y pie, 8 materiales y 2 de mano de obra | feliz | `CA-1` | `HDU-001 esc. 5` |
| TC-41 | `test_hdu001_esc05_analisis_reales_de_union_square` (real): 20; las cuatro hojas ajenas sin análisis ni hallazgo; `"MURO STD-635-STD "` reconocida | feliz | `CA-2` | `HDU-001 esc. 5` |
| TC-42 | `test_hdu001_esc05_muro_std_635_std` (real): cabecera, el insumo `CANAL 635X3.05 CAL.26` y las dos cuadrillas con las cifras de `CA-3`, los cargos de `CA-4` y los totales con los literales exactos de E-5 (P3); reconstruido a menos de `1E-9` del pie | feliz | `CA-3`, `CA-4`, `CA-16` | `HDU-001 esc. 5` |
| TC-43 | `test_hdu001_esc06_siroc_real` (real): 20 `CARGO_DESCONOCIDO` en ENITI, uno por hoja, columna `A`, `SIROC`; ningún cargo `SIROC` con tipo | **rechazo** | `CA-6` | `HDU-001 esc. 6` |
| TC-44 | `test_hdu001_esc07_analisis_reales_sin_codigo` (real): 21 `ANALISIS_SIN_CODIGO` (1 en ENITI, 20 en Union), fila 12, columna `C`; ninguna asociación en Union | **rechazo** | `CA-7` | `HDU-001 esc. 7` |
| TC-45 | `test_hdu001_esc09_codigos_reales_en_dos_hojas` (real): seis `CODIGO_EN_VARIAS_HOJAS` para `620014`, `620045` y `620050`, cada uno con la otra hoja | **rechazo** | `CA-8` | `HDU-001 esc. 9` |
| TC-46 | `test_hdu001_esc06_ref_real_en_pu_de_cabecera` (real): `ERROR_DE_FORMULA` en fila 15, columna `C`, `#REF!` en las hojas `14`, `15`, `16`, `18` y `19`, y ninguna de ellas con hallazgo de cuadre | **rechazo** | `CA-9` | `HDU-001 esc. 6` |
| TC-47 | `test_hdu001_esc06_las_44_hojas_reales_cuadran` (real): cero `PU_NO_CUADRA` y cero `PU_NO_VERIFICABLE` en los dos libros | **rechazo** (oráculo) | `CA-10` | `HDU-001 esc. 6` |
| TC-48 | `test_hdu001_esc05_asociacion_real_de_eniti` (real): `01` → 162 filas; `40-A` → `620040-A`; 16 códigos sin análisis | feliz | `CA-5` | `HDU-001 esc. 5` |
| TC-49 | `test_hdu001_esc10_insumos_reales_por_crear` (real): con mapa vacío, 29 en ENITI (26 y 3) y 23 en Union (21 y 2); unión de claves 35 y comunes 17; con `{"CANAL 635X3.05 CAL.26": "PZA"}`, ese insumo no aparece | feliz | `CA-12` | `HDU-001 esc. 10` |
| TC-INV-3 | Suite de TKT-013 sin cambios (`tests/test_tkt013_*.py`), con y sin las variables: 5,028 y 4,281 conceptos, y `inspect.signature(leer_catalogo)` con un solo parámetro | regresión | `CA-R3` | — |
| TC-INV-4 | `test_tkt014_car1_tipos_sincronizados`: los valores de `TipoCargo` iguales a los de `pg_get_constraintdef` de `ck_apu_cargo_tipo`, y los de `TipoInsumo` contenidos en los de `ck_insumo_tipo` (rol de migración) | regresión | `CA-4`, `M3` | — |

No hay prueba de concurrencia: el lector no bloquea ni escribe.

### Mutación

Cada mutante se aplica a mano, se ejecuta la prueba indicada, se ve en rojo y se revierte. Lo que se mutó y qué cayó se pega en `impl.md`.

| # | Mutante | Test que debe ponerse rojo |
|---|---|---|
| M-01 | `<=` por `<` en la tolerancia | TC-16 (`158.94`) |
| M-02 | Tolerancia `0.1` en lugar de `0.01` | TC-16 (`158.9400001`) |
| M-03 | Sin `abs()` en la diferencia | TC-16 (`158.9400001`) |
| M-04 | Cuantizar archivo y reconstruido antes de comparar | TC-16 (`158.9400001`) |
| M-05 | Verificar contra el P.U. de la cabecera en vez del pie | TC-13 |
| M-06 | Los cargos sin tipo no entran en la suma | TC-12 |
| M-07 | `IVA` por igualdad exacta en lugar de prefijo | TC-03 (`IVA 16% MATERIALES`) |
| M-08 | Rótulo desconocido mapeado a `INDIRECTOS` | TC-04 y TC-12 |
| M-09 | `rotulo_normalizado` sin `rstrip(":")` | TC-09 (`MATERIAL:`) |
| M-10 | Una fila sin cifras en E, F y G se lee como insumo | TC-09 (fila `SACO`) |
| M-11 | Sin los prefijos de subtotal | TC-11 |
| M-12 | `_interpretar_no_negativo` sin la comprobación del signo | TC-14 |
| M-13 | Un total ilegible se suma como cero | TC-15 |
| M-14 | `normalizar_clave_insumo` con `strip().upper()`, sin colapsar | TC-01 y TC-28 |
| M-15 | Un conflicto de unidad se resuelve con la primera | TC-30 |
| M-16 | Un código en dos hojas asocia la primera | TC-26 |
| M-17 | `leer_libro_presupuesto` llama a `leer_catalogo(contenido)` y vuelve a abrir | TC-35 |
| M-18 | El bloque de viáticos no se cierra ante un rótulo con tipo | TC-10 |

## Impacto

Análisis del arquitecto; `revisor-impacto` lo revisa antes del gate.

| Qué se toca | Quién depende | Riesgo | Mitigación |
|---|---|---|---|
| `lector_catalogo.py`, refactor (b) | TKT-013 y sus 47 pruebas; TKT-015 y TKT-018 | Cambiar sin querer la lectura del catálogo | Extracción sin editar instrucciones; TC-INV-3 con los dos archivos reales y TC-34 compara con `leer_catalogo` |
| `CausaHallazgo` con diez miembros más (a y b) | TKT-015, que traduce causas | Una causa sin traducción | Tabla de causas en este diseño; TKT-015 la hereda |
| `interpretar_numero` con cuatro tipos (a) | El catálogo | Un error de tipos en mypy en las llamadas de TKT-013 | La firma solo amplía; `uv run mypy .` en A1 |
| `AnalisisDelLibro` como contrato interno (b) | TKT-015, TKT-016, TKT-017 y TKT-018 | Cambiar sus campos obliga a tocar a los cuatro | Inmutable y tipado; E-9 anota que viaja por `pickle` |
| La clave de insumo por descripción | TKT-010 (semilla `TBR-001` a `TBR-027`), TKT-017 | Los sembrados no coinciden con los reales y salen «por crear»; duplicados por errores tipográficos (`PA-T1`) | ADR-034 y la documentación del mismo cambio; lo vigila la previsualización de TKT-018 |
| Valores negativos con hallazgo en el APU, sin él en el catálogo | TKT-015 | Criterios distintos entre lectores | El APU lo exige `M8`; el catálogo quedó así en TKT-013 (observación 5 de su impacto) |

**Fronteras entre módulos:** No. Todo el código nuevo vive en `presupuesto`; `dominio/` solo importa la biblioteca estándar y `tipos_base`; `infraestructura/` importa `dominio/` y openpyxl; nada se publica en `interfaz.py`. Los contratos de `import-linter` no cambian.

### Revisión de impacto

`revisor-impacto` revisó el diseño el 2026-11-02. Veredicto: **sin frontera cruzada**, con ocho omisiones que este diseño incorpora. `uv run lint-imports` dio «15 kept, 0 broken» y ninguna prueba, herramienta ni documento enumera `CausaHallazgo`.

| # | Omisión | Qué se hace |
|---|---|---|
| 1 | El `Grep` de B4 busca «33 decisiones», pero solo `CLAUDE.md:14` usa esa frase; `README.md:30` y `llms.txt:27` dicen «33 ADRs» | El patrón de B4 es `33 (decisiones\|ADRs)`. B4 corre también `python -m unittest discover -s tools/tests`, cuya prueba `test_definicion_revision.py` cuenta los archivos de `docs/adr/` y exige que los tres documentos citen el número real, y añade la fila de ADR-034 en `docs/adr/README.md` |
| 2 | `insumo.codigo` es `NOT NULL` y `UNIQUE`, y `InsumoPorCrear` no lleva código: nadie dice de dónde nace | **Pregunta P14 para la persona dueña.** Mientras no se resuelva, `InsumoPorCrear` no inventa código y TKT-017 no puede materializar. `docs/03-modelo-datos.md:231,237` entra en «Documentación afectada» |
| 3 | `docs/05:673` (TKT-015) y `:698` (TKT-016) dicen «Depende de TKT-014»; `docs/05:494` dice que TKT-014 «encuentra sus insumos» | Se cambian a «Depende de TKT-014b» y a la redacción de la nueva clave, en la fila B4 |
| 4 | `backend/tests/test_tkt010_semilla_local.py:259-264` afirma que los 27 códigos sembrados «ya son lo que el importador buscaría» | Ese texto queda falso. B4 corrige el nombre y el docstring sin cambiar la aserción, porque quien escribe el código no toca los tests: lo hace `tester-backend` |
| 5 | `docs/arranque-local.md` (sección de TKT-013) y el docstring de `conftest.py:1177-1181` no mencionan las hojas de APU | B4 añade `test_tkt014_archivos_reales.py` a esa sección y avisa de que el libro de Union debe traer las hojas de APU |
| 6 | Las causas `PU_NO_CUADRA`, `CARGO_DESCONOCIDO` y `ANALISIS_SIN_CODIGO` no caben en los siete tipos de `ck_importacion_error_tipo` | Queda como entrada para TKT-015: o una decisión de esquema, o una política de descarte. Se anota en `_index.md` como ticket futuro |
| 7 | La suite de TKT-013 tiene 53 funciones de prueba, no 47. Los nombres `esc07` y `esc09` de TC-25 y TC-26 chocan con los escenarios 7 y 9 de HDU-001 (concepto sin análisis, código duplicado), que `tools/verificar_escenarios.py` acreditaría | Se corrige la cifra. El tester conserva `esc07` y `esc09` solo en las pruebas que sí cubren esos escenarios; las demás llevan `hdu001_esc06` o `esc10`, según corresponda |
| 8 | `_normalizar_rotulo` no quita el tabulador ni el espacio duro interior | E-2 lo detecta en los reales; si aparece, se escala |

## Documentación afectada

| Documento | Qué cambia | Ticket |
|---|---|---|
| `docs/03-modelo-datos.md` (`:231`, `:237`) | La descripción de `insumo` y de `creado_en_importacion`: el insumo lo propone TKT-014 y lo escribe TKT-017; la clave de comparación es la descripción normalizada. El origen del `codigo` según P14 | b |
| `docs/05-tickets-trabajo.md`, TKT-015 (`:673`), TKT-016 (`:698`) y TKT-010 (`:494`) | «Depende de TKT-014» pasa a «Depende de TKT-014b»; «TKT-014 encuentra sus insumos» pasa a la nueva clave | b |
| `docs/05-tickets-trabajo.md`, ficha de TKT-014 (`:649`) | Subsección «Partición en dos tickets hermanos» con la tabla de este diseño. Los criterios: «Asocia cada análisis con su concepto» pasa a «por el código de la hoja; sin código o con el código en dos hojas, lo reporta»; «Da de alta los insumos que no existan» pasa a «Devuelve los insumos por crear, por descripción normalizada, marcados `creado_en_importacion = true`; los da de alta TKT-017»; «dentro de la tolerancia decimal» pasa a «dentro de ±0.01 absoluta `(asumido)`» | a |
| `docs/05-tickets-trabajo.md`, TKT-010 (`:502`) | «La clave del importador es el `codigo` recortado y en mayúsculas» pasa a «La clave del importador es la descripción recortada, en mayúsculas y con los espacios interiores colapsados (decisión del 2026-11-02, ADR-034): los 27 códigos sembrados no la cumplen y saldrán por crear (`PA-T1` de TKT-014)» | b |
| `docs/05-tickets-trabajo.md`, TKT-011 (`:576`) | «que TKT-014 marca al dar de alta» pasa a «que TKT-017 marca al dar de alta un insumo que TKT-014 propone» | b |
| `docs/adr/20261102-semilla-en-migracion-y-herramienta-local.md` (`:51`) | Se añade, bajo «Cuándo revisar», que la condición se cumplió: TKT-014 eligió la descripción normalizada (ADR-034), y que la regla de clave de la semilla queda pendiente de TKT-017 | b |
| `docs/adr/` y `docs/adr/README.md` | ADR-034 con su fila en el índice | b |
| `CLAUDE.md` (`:14`), `README.md` y `llms.txt` | «33 decisiones» pasa a 34. B4 corre un `Grep` y pega la salida en `impl.md`. El cambio de `CLAUDE.md` lo aprueba la persona dueña (P11) | b |
| `docs/arranque-local.md` | `CIMENTA_CATALOGO_UNION` debe apuntar al libro `AP-058-25 SEGUNDA ETAPA P.U UNION SQUERE.xlsx`, que trae las hojas de APU | b |
| `sdd/tickets/tkt-014/spec.md` | Ajustes de «Criterios de la spec que hay que ajustar»; las cifras de `CA-10` (P2) y de `CA-3` y `CA-16` (P3); `PA-T10` pasa a resuelta con referencia a este diseño | a |
| `sdd/tickets/tkt-014/_index.md` y `sdd/_evolucion.md` | Dos ramas (`tkt-014a-…` y `tkt-014b-…`), el log de la partición y las observaciones de cada entrega | a y b |

## ¿Merece ADR?

Sí, uno, en formato MADR, creado en la fila B4:

- **ADR-034** · `docs/adr/<fecha de B4>-clave-de-insumo-y-lectura-de-apu.md`. Un recién llegado preguntará por qué un insumo se identifica por su descripción, por qué la hoja se lee por rótulo de fila con columnas fijas y por qué el cuadre suma lo leído en vez de recalcular. Opciones de clave: código de insumo (decisión A2, imposible porque las hojas no lo traen), descripción normalizada (elegida), descripción más unidad, mapa manual de la Dirección. Opciones de lectura: posiciones fijas, rótulos de fila con columnas fijas (elegida), rótulos de columna. Opciones de cuadre: recalcular `costo × rendimiento` y `porcentaje × base`, sumar lo leído (elegida). Consecuencias: `PA-T1` (errores tipográficos y semilla sin coincidencias), `PA-T6` (el cuadre no detecta un cargo mal calculado), y que la tolerancia vive en el dominio y no en `tipos_base`.

La partición no necesita ADR: queda en la ficha de `docs/05`, como en TKT-013.

## Pasada adversarial

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Crítica | `CA-10` dice que un pie de `641.37` frente a un reconstruido de `641.3608310977561` da hallazgo, pero la diferencia es `0.0091689…`, menor que `0.01`: con la tolerancia aprobada **cuadra**. El criterio contradice la decisión 4 | P2: cambiar la cifra del criterio a `641.38` (diferencia `0.0191689…`). TC-17 se escribe con `641.38` |
| 2 | Alta | Las cifras de `CA-3` y `CA-16` vienen de la aritmética `float` del Excel; la suma exacta de los `Decimal(repr(f))` puede diferir en el decimal quince. Como en TKT-013 con `16.089000000000002`, el criterio fallaría sin defecto en el lector | E-5 mide los totales exactos; P3 propone que los literales de TC-42 salgan de E-5 y que el P.U. reconstruido se compruebe a menos de `1E-9` del pie |
| 3 | Alta | La disposición de la hoja (columnas de base, porcentaje, fecha, analista y unidad de cabecera) no se ha visto al diseñar | E-1 y E-2 la miden en A0 con condiciones de parada explícitas; TC-47 (las 44 hojas cuadran) es el oráculo final: un subtotal leído como cargo descuadra la hoja |
| 4 | Alta | Una fila con descripción y sin ninguna cifra se salta en silencio: si un insumo real trae las tres celdas vacías, desaparece | E-2 cuenta esas filas en los reales; P9 pide aceptarlo. Un insumo con una sola cifra sí se lee y reporta las otras |
| 5 | Media | Importar privados de `lectura_catalogo.py` acopla los dos lectores | Mismo paquete y misma capa; renombrar tocaría TKT-013 sin cambiar comportamiento. Si cambian, la suite de ambos lo detecta |
| 6 | Media | Las claves existentes se suponen normalizadas: si TKT-017 las guarda sin normalizar, nada coincide | P12; `normalizar_clave_insumo` es pública para que quien arme el mapa use la misma |
| 7 | Media | `VALOR_AUSENTE` en base y porcentaje vacíos puede dar ruido en los viáticos de 44 hojas | E-1 lo mide; P13. Las columnas son `NOT NULL`: es un hallazgo real para TKT-017 |
| 8 | Baja | La fecha como cadena depende de la forma que produce `str(datetime)` en `_a_valor_celda` | E-6 la confirma; TC-36 la prueba de extremo a extremo |

## Riesgos

| Riesgo | Probabilidad | Impacto | Qué se hace |
|---|---|---|---|
| E-1 o E-2 muestran columnas o rótulos que varían entre hojas | Media | Alto: la lectura por columnas fijas no sirve | `/sdd-escalar` antes de A1 con las variantes encontradas |
| E-3 reconoce `REFUERZOS` o `RESUMEN US F2` como APU | Baja | Medio: `CA-2` falla | `/sdd-escalar` antes de A1 |
| E-4 encuentra conflictos de unidad o de tipo en los reales | Media | Medio: las cuentas de `CA-12` cambian | `/sdd-escalar` antes de B3, con las claves en conflicto |
| Una hoja real no cuadra por un subtotal no previsto | Media | Medio | TC-47 lo detecta; se añade el rótulo a los prefijos solo con aprobación, vía `/sdd-escalar` |
| El tamaño de cada PR (~830 y ~935) sigue por encima del tope | Cierta | Medio | Precedente de TKT-011 y TKT-013 |

## Preguntas para el gate

| # | Pregunta | Recomendación |
|---|---|---|
| P1 | ¿Se parte en TKT-014a (dominio de la hoja) y TKT-014b (asociación, insumos, adaptador, reales y documentación), con un PR cada uno y fusión a → b? | Sí: ~1,765 líneas en un PR cuadruplican el tope; precedente de TKT-013 |
| P2 | El ejemplo de `CA-10` cuadra con la tolerancia aprobada. ¿Se cambia el pie del ejemplo a `641.38`? | Sí: conserva el caso y la decisión 4; la frontera exacta la prueban `0.01` y `0.0100001` |
| P3 | ¿Los literales de material, costo directo y P.U. reconstruido de `CA-3` y `CA-16` se toman de la suma exacta que mida E-5, y «igual al del archivo» se lee como «a menos de `1E-9`»? | Sí: el lector suma con precisión completa lo que el Excel sumó en `float`; forzar la igualdad obligaría a redondear |
| P4 | Un código en dos hojas: ¿se deja **sin asociar** en las dos (con su hallazgo), en vez de asociar ambas? | Sin asociar: asociar las dos daría dos APU a un concepto, que el modelo no admite, y la decisión 2 dice «no se elige» |
| P5 | Un código de hoja que no está en el catálogo: ¿hallazgo `CODIGO_SIN_CONCEPTO`? | Sí: si no, el análisis queda sin asociar en silencio |
| P6 | Una misma clave en el bloque de material y en el de mano de obra: ¿hallazgo `TIPO_EN_CONFLICTO` y no se propone? | Sí: mismo criterio que la unidad en conflicto (`CA-14`); no se adivina el tipo |
| P7 | ¿Se confirma que el cuadre suma el cargo y el importe leídos, sin recalcular `costo × rendimiento` ni `porcentaje × base`? | Sí: es lo que piden la decisión 5, `PA-T6` y la objeción 2 de la spec |
| P8 | ¿La fecha viaja como cadena `AAAA-MM-DD` y no como `date`? | Sí: la regla 2 de `CLAUDE.md` excluye `datetime` del dominio; TKT-017 la convierte |
| P9 | Filas con texto en A y sin cifras en E, F y G se ignoran sin hallazgo; filas que empiezan por `SUBTOTAL`, `TOTAL` o `SUMA`, también. ¿De acuerdo? | Sí: son encabezados, filas extra de unidad y subtotales; E-2 lo comprueba en los reales y TC-47 vigila el cuadre |
| P10 | ¿`VALOR_NEGATIVO` como causa nueva, con el campo en `None`? | Sí: `M8` lo pide y el esquema lo rechazaría al materializar |
| P11 | ¿Se aprueba ADR-034 y editar el conteo de ADR en `CLAUDE.md`, `README.md` y `llms.txt`? | Sí, en TKT-014b |
| P12 | ¿El lector recibe `insumos_existentes` como `clave normalizada → unidad`, y quien arma el mapa normaliza con `normalizar_clave_insumo`? | Sí: una sola función de clave y ninguna consulta a la base |
| P13 | Base o porcentaje vacíos en un cargo dan `VALOR_AUSENTE`. ¿De acuerdo, aunque aparezca en los viáticos? | Sí: las tres columnas de `apu_cargo` son `NOT NULL`; ocultarlo solo lo aplaza a TKT-017 |
| P14 | `insumo.codigo` es `NOT NULL` y `UNIQUE`, y las hojas no traen código. ¿De dónde sale el código de un insumo nuevo? (surgió de la revisión de impacto) | Dejarlo fuera de TKT-014: `InsumoPorCrear` no lleva código y es TKT-017 quien lo genera con una regla propia (por ejemplo, `IMP-` y un consecutivo), que la persona dueña confirma al definirlo. Se anota como ticket futuro y como `PA-T13` de la spec |
