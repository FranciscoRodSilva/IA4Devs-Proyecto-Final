# Spec · TKT-014 · Lector de análisis de precios unitarios

> [← index](_index.md) | Siguiente: `design.md` (lo escribe `/sdd-disenar`)

## Contexto y problema

La importación de la línea base (HDU-001) lee dos cosas del Excel: el catálogo de conceptos, que ya lee TKT-013, y el análisis de precio unitario (APU) de cada concepto, que hoy no lee nada. Sin los APU no hay costo directo, ni rendimientos, ni explosión de insumos (TKT-016), ni líneas base materializables (TKT-017). TKT-014 construye ese lector. Es un lector en memoria, igual que el de TKT-013: devuelve un valor, no escribe en la base y no clasifica los hallazgos en los tipos de `importacion_error`, que es trabajo de TKT-015.

Lo que muestran las hojas de APU de los dos archivos reales, medido el 2026-11-02 sobre las copias de `D:\Documentos\Miich\Documentos\`, y que condiciona la especificación:

| | ENITI Torre 5 | Union Square F2 (`AP-058-25 SEGUNDA ETAPA P.U UNION SQUERE.xlsx`) |
|---|---|---|
| Hojas que no son catálogo | 24, todas de APU | 23: 20 de APU, más `RESUMEN US F2`, `BORRADOR DE GENERADORES` y `REFUERZOS`, que no son APU |
| Hojas de APU con código de concepto | 23 de 24 (`NICHO DE TOMAS DE GAS` no lo trae) | 0 de 20: `CODIGO` vacío y `CONCEPTO` con `#REF!` en todas |
| Códigos distintos en las hojas de APU | 20; el `620014`, el `620045` y el `620050` aparecen en dos hojas cada uno | ninguno |
| Códigos del catálogo sin hoja de APU | 16 de 36 | los 31 |
| P.U. de la cabecera (`P.U:`, fila 15) | `#REF!` en 5 hojas (`14`, `15`, `16`, `18`, `19`) | numérico en las 20 |
| Cargos fuera de los siete tipos del CHECK | `SIROC`, 1 %, en 20 hojas | ninguno |
| Cargo de IVA | rótulo `IVA` en 9 hojas e `IVA 16% MATERIALES` en 15 | rótulo `IVA` en las 20 |
| Insumos distintos (descripción recortada, en mayúsculas y con espacios internos colapsados) | 29: 26 de material y 3 de mano de obra | 23: 21 de material y 2 de mano de obra; 17 coinciden con los de ENITI y la unión de ambos es de 35 |
| Unidades de insumo | `PZA`, `ROLLO`, `CAJA`, `SACO`, `KG`, `ML` y `JORNAL`, todas dentro de las ocho del invariante 27 | las mismas, sin `ML` |

Hallazgos de estructura:

- **Las hojas de APU no traen código por insumo.** Cada renglón de material o de mano de obra trae descripción, unidad, costo, rendimiento y cargo, nada más. La decisión **A2** del 2026-11-02 daba por hecho un código por insumo, y los archivos reales lo desmienten. La persona dueña resolvió el mismo día que la clave pase a ser la descripción normalizada (ver la decisión 1 de «Preguntas abiertas y supuestos»).
- **Las hojas se leen por rótulo, no por posición.** Las filas de un mismo bloque cambian de lugar entre hojas (el pie `PRECIO UNITARIO` está en la fila 60 de Union y en la 61 de ENITI), y algunas hojas traen una fila extra, como `SACO` o `KG`, entre el encabezado y los materiales.
- **El rendimiento de la mano de obra no sigue la fórmula del glosario.** Para el material, `cargo = costo × rendimiento`. Para la mano de obra, el cargo es `costo ÷ rendimiento`: `CUADRILLA DE PINTOR`, 1,152.39 ÷ 4.1 = 281.07. Y en la hoja `MURO STD-635-STD`, la `CUADRILLA DE LIMPIEZA` trae costo 864.4, rendimiento 5 y cargo 5, que no sigue ninguna de las dos fórmulas. El lector lee estas cifras tal como vienen y deja la semántica como supuesto abierto (`PA-T6`).
- **El P.U. de la hoja se cierra con el IVA dentro.** `IVA` es un cargo indirecto y forma parte del precio unitario del archivo. Que eso dependa de `obra.iva_acreditable` (`RN-25`) lo decide quien materialice, no el lector.

## Historia de usuario

**Como** Director de Proyectos
**quiero** que el sistema lea el análisis de precio unitario de cada concepto de mi Excel, con sus insumos, rendimientos y cargos, y verifique que cuadra con el precio del archivo
**para** poder revisar lo que se va a importar y detectar un análisis roto antes de aceptarlo, sin que nada se escriba todavía en el modelo real.

## Alcance

| Nivel | Ítem |
|---|---|
| **Must** | **M1.** Reconocer por sus rótulos las hojas de APU de un libro y leer sus bloques (cabecera, material, mano de obra, costo directo, cargos porcentuales, viáticos y hospedaje, cargos indirectos y precio unitario), sin posiciones fijas, de modo que lea los dos archivos reales. Las hojas que no tienen esa estructura se ignoran sin hallazgo |
| **Must** | **M2.** Leer la cabecera de cada análisis: código del concepto (recortado y en mayúsculas), unidad normalizada contra las ocho del catálogo, fecha, analista y P.U. del archivo |
| **Must** | **M3.** Leer cada insumo de los bloques de material y de mano de obra: descripción, unidad, costo unitario, rendimiento y cargo, con el bloque que determina su tipo (`MATERIAL` o `MANO_OBRA`) |
| **Must** | **M4.** Leer cada cargo con su tipo, porcentaje, base e importe. El tipo sale del rótulo, contra los siete del CHECK de `apu_cargo`; un rótulo fuera de ellos se reporta y no se le inventa tipo |
| **Must** | **M5.** Asociar cada análisis con su concepto solo por el código de la hoja. Sin código, o con `#REF!`, el análisis queda sin asociar y con hallazgo; un código en dos hojas conserva ambas y reporta la ambigüedad |
| **Must** | **M6.** Devolver los insumos por crear: los que no existen según una lista de claves que recibe el lector, marcados `creado_en_importacion = true`, sin tocar la base |
| **Must** | **M7.** Verificar que el precio unitario reconstruido con lo leído coincide con el P.U. del archivo dentro de ±0.01 absoluta; si no, hallazgo bloqueante |
| **Must** | **M8.** Reportar hoja, fila, columna y valor original de todo valor que no pueda interpretar (`#REF!`, texto en columna numérica, rendimiento ausente, negativo), sin sustituirlo por cero |
| **Must** | **M9.** Devolver el resultado como valor en memoria, con todo el dinero, las cantidades y los porcentajes en `Decimal`, sin abrir conexión a la base, y probarlo contra los dos archivos reales además de contra libros sintéticos |
| **Should** | **S1.** Totales por análisis reconstruidos de las líneas leídas (material, mano de obra, costo directo, cargos y P.U.), para la previsualización |
| **Could** | — |
| **Won't** | Clasificar hallazgos en `REF_ROTA`, `SIN_APU`, `RENDIMIENTO_AUSENTE`, `DUPLICADO` y los demás tipos de `importacion_error` (TKT-015) · decidir cuáles códigos del catálogo carecen de análisis, o si falta un análisis (`SIN_APU`) · escribir insumos, precios, APU o cargos en la base (TKT-017) · crear o actualizar `precio_insumo` · ampliar el CHECK de `apu_cargo.tipo` para `SIROC` · decidir el sentido del rendimiento de la mano de obra (TKT-016) · resolver los códigos repetidos del catálogo (`PA-T1` de TKT-013) · asociar por nombre de hoja o por descripción · recalcular precios · rutas, orquestación y estado de la importación (TKT-018) · confirmar o materializar (TKT-017) · validar el archivo por sus bytes (TKT-059) · pantallas |

## Partición en dos entregas

La persona dueña aprobó el 2026-11-02 partir el ticket en dos entregas con un PR cada una, como TKT-013. El orden de fusión es fijo: **TKT-014a y después TKT-014b**. TKT-014 queda como paraguas, conserva esta spec y el diseño, y se cierra cuando se cierran las dos. TKT-015, TKT-016 y TKT-017 pasan a depender de TKT-014b.

| Entrega | Contenido |
|---|---|
| TKT-014a | Dominio de la hoja, sin archivos externos: `M1` a `M4`, `M7`, `M8` y `S1` sobre filas en memoria, y las cifras en `Decimal` de `M9` |
| TKT-014b | Asociación (`M5`), insumos por crear (`M6`), el adaptador openpyxl, las pruebas contra los archivos reales y ADR-034 |

Cómo se reparten los criterios: `CA-1`, `CA-2`, `CA-5`, `CA-7`, `CA-8`, `CA-9`, `CA-12` y `CA-14` son de TKT-014b. `CA-3`, `CA-4`, `CA-6` y `CA-16` los cubre TKT-014a con una hoja sintética de la misma forma, y TKT-014b los repite contra el archivo real. `CA-10`, `CA-11` y `CA-13` los cubre TKT-014a con filas en memoria, y TKT-014b repite `CA-10` sobre las 44 hojas reales. `CA-15` se divide entre las cifras en `Decimal` (014a) y la base intacta y la lectura determinista (014b). `CA-R3` es solo de TKT-014b. Las cifras exactas de `CA-3` y `CA-16` salen de la medición E-5 del diseño, y «igual al del archivo» se lee como una diferencia menor que 1E-9 (P3).

## Non-goals

- No escribe en ninguna tabla ni abre sesión de base de datos. Las claves de los insumos existentes llegan como dato; el lector no las consulta.
- No decide el estado de la importación: que quede `CON_ERRORES` lo decide TKT-015.
- No recalcula precios: reconstruye el P.U. solo para verificar el del archivo, y nunca lo sustituye.
- No adivina: ni el código de un análisis sin código, ni el tipo de un cargo desconocido, ni la unidad de un insumo, ni el valor de una celda rota.
- No lee el catálogo de conceptos: lo recibe ya leído por TKT-013.
- No acepta archivos que no hayan pasado la validación por bytes del módulo `archivos` (TKT-059, ADR-016 regla 3).
- No cambia el modelo de datos, el borrador OpenAPI ni el catálogo de tipos de error.

## Reglas de negocio implicadas

Ninguna `RN-xx` gobierna la lectura. El requisito es F1.2 del PRD: importar el análisis de precio unitario de cada concepto con insumos, costos unitarios, rendimientos y cargos porcentuales.

| Regla | Qué exige | Dónde está |
|---|---|---|
| `RN-01` | Nada se escribe en el modelo real antes de confirmar. El lector solo la respeta por omisión: no escribe, y por eso el alta de insumos queda para TKT-017 | PRD §8 — `docs/01-descripcion-producto.md` |
| `RN-24` | La línea base conserva el rendimiento congelado. El rendimiento que lee este ticket es la fuente de ese valor (TKT-016); el lector no lo redondea ni lo corrige | PRD §8 |
| `RN-25` | El IVA no acreditable forma parte del costo y permanece dentro del precio unitario, según la obra. El lector lee el cargo `IVA` tal como viene y no decide su tratamiento | PRD §8 |
| Regla 1 de `CLAUDE.md` | El dinero nunca es flotante: las cifras del Excel llegan como `float` y salen como `Decimal` | `CLAUDE.md` |
| Invariante 27 | `insumo.unidad` solo admite las ocho unidades del catálogo cerrado | `docs/03-modelo-datos.md` |

El escenario de rechazo de este ticket no cuelga de una `RN`, sino de la regla 1 de `CLAUDE.md`, del invariante 27 y de HDU-001 esc. 6, 7, 8 y 10: el valor que no se puede interpretar, el cargo desconocido y el P.U. que no cuadra se reportan con su ubicación y no se sustituyen por un valor inventado.

## Invariantes que deben sobrevivir al cambio

El ticket añade un lector y reutiliza piezas de TKT-013. Estas garantías ya vigentes no pueden romperse.

| Invariante | Qué protege | Criterio de regresión |
|---|---|---|
| Regla 2 de `CLAUDE.md` | `dominio/` no importa `openpyxl` ni ningún paquete de terceros | `CA-R1` |
| Regla 3 de `CLAUDE.md` | Ningún módulo cruza la frontera de otro por su infraestructura | `CA-R1` |
| Regla 1 de `CLAUDE.md` | Ningún `float` en firmas de `dominio/` ni de `tipos_base/` | `CA-R2` |
| Lector del catálogo (TKT-013, ADR-033) | El lector de catálogo sigue devolviendo las mismas cifras sobre los dos archivos reales | `CA-R3` |
| Invariante 27 | Un insumo solo se propone con una de las ocho unidades | `CA-14` |

## Criterios de aceptación

Las cifras salen de la medición del 2026-11-02 (ver «Contexto y problema») y el diseño las reconfirma en su fila de arranque, en particular los conteos de insumos, que usan una normalización que el lector todavía no tiene. Los archivos reales no se versionan; en CI corre un libro sintético con la misma estructura (`PA-T3` de TKT-013) y las variables `CIMENTA_CATALOGO_ENITI` y `CIMENTA_CATALOGO_UNION` apuntan al libro de Union que trae las hojas de APU.

### CA-1 `[M]` · Reconoce las hojas de APU de ENITI · F1.2

```gherkin
Escenario: El lector encuentra los 24 análisis de ENITI
  Dado el archivo "Presupuesto Base Tablaroca Eniti T5 AP 2.xlsx"
  Cuando el lector analiza sus hojas de APU
  Entonces devuelve 24 análisis, en el orden de las hojas
  Y la hoja "CATALOGO" no se interpreta como análisis
  Y el primer análisis es la hoja "01", con código "620001", unidad "M2", fecha 2026-08-25 y P.U. 668.6929342319413
  Y el análisis de la hoja "01" trae 8 materiales y 2 insumos de mano de obra
```

### CA-2 `[M]` · Reconoce las hojas de APU de Union Square e ignora las demás · F1.2

```gherkin
Escenario: El lector encuentra los 20 análisis de Union Square y salta las hojas ajenas
  Dado el archivo "AP-058-25 SEGUNDA ETAPA P.U UNION SQUERE.xlsx"
  Cuando el lector analiza sus hojas de APU
  Entonces devuelve 20 análisis
  Y "RESUMEN US F2", "BORRADOR DE GENERADORES", "REFUERZOS" y "CATALOGO DE CONCEPTOS" no producen análisis ni hallazgo
  Y la hoja "MURO STD-635-STD " se reconoce aunque el nombre termine en un espacio
```

### CA-3 `[M]` · Lee un análisis completo: MURO STD-635-STD · F1.2

```gherkin
Escenario: El análisis de MURO STD-635-STD se lee con sus cifras exactas
  Dado la hoja "MURO STD-635-STD " del archivo de Union Square
  Cuando el lector la analiza
  Entonces la cabecera trae unidad "M2", fecha 2025-09-01, analista "ARQ.MAXIMILIANO QUEZADA GARCIA" y P.U. 641.3608310977561
  Y el bloque de material trae 8 insumos, entre ellos "CANAL 635X3.05 CAL.26", unidad "PZA", costo 44.58, rendimiento 0.3278 y cargo 14.613323999999999
  Y el bloque de mano de obra trae "CUADRILLA DE PINTOR", unidad "JORNAL", costo 1152.39, rendimiento 4.1 y cargo 281.0707317073171, y "CUADRILLA DE LIMPIEZA", costo 864.4, rendimiento 5 y cargo 5, tal como vienen
  Y el material suma 201.669152, la mano de obra 286.0707317073171 y el costo directo 487.7398837073171
  Y el P.U. reconstruido es 641.3608310977561, igual al del archivo
```

### CA-4 `[M]` · Lee los cargos con su tipo, porcentaje, base e importe · F1.2

```gherkin
Escenario: Los cargos de MURO STD-635-STD salen tipificados
  Dado la hoja "MURO STD-635-STD " del archivo de Union Square
  Cuando el lector lee sus cargos
  Entonces "HERRAMIENTA MENOR" es de tipo HERRAMIENTA_MENOR, porcentaje 0.01, base 487.7398837073171 e importe 4.877398837073171
  Y "ANDAMIAJE" es de tipo ANDAMIAJE y "DESPERDICIO" es de tipo DESPERDICIO, porcentaje 0.05, base 201.669152 e importe 10.0834576
  Y "OFICIAL TABLAROQUERO" y "AYUDANTE TABLAROQUERO", del bloque de viáticos, son de tipo VIATICOS, porcentaje 0 e importe 0
  Y "IVA" es de tipo IVA con porcentaje 0.16, "INDIRECTOS" de tipo INDIRECTOS con 0.08 y base 507.57813898146344, y "UTILIDAD" de tipo UTILIDAD con 0.12
  Y el rótulo "IVA 16% MATERIALES" de ENITI se lee como tipo IVA
```

### CA-5 `[M]` · Asocia el análisis con su concepto por el código · F1.2

```gherkin
Escenario: El código de la hoja liga el análisis con las filas del catálogo
  Dado el catálogo de ENITI ya leído por TKT-013 y sus hojas de APU
  Cuando el lector asocia cada análisis con su concepto
  Entonces la hoja "01", con código "620001", queda asociada a las 162 filas del catálogo con ese código
  Y la hoja "40-A", con código "620040-A", conserva el sufijo como texto y se asocia al catálogo con ese código
  Y el código numérico 620001 de la celda se compara como el texto "620001"
  Y los 16 códigos del catálogo sin hoja se exponen como lista, sin hallazgo, porque clasificar "SIN_APU" es de TKT-015
```

### CA-6 `[M]` · Rechazo · Cargo que no está entre los siete tipos · `HDU-001 esc. 6`

```gherkin
Escenario: SIROC se reporta como tipo desconocido y se conserva
  Dado las 20 hojas de ENITI que traen el cargo "SIROC" al 1 %
  Cuando el lector lee sus cargos
  Entonces conserva el cargo con su rótulo, porcentaje 0.01, base e importe, sin tipo
  Y reporta un hallazgo por hoja con hoja, fila, columna "A", valor original "SIROC" y la causa "tipo de cargo desconocido"
  Y el cargo cuenta en el P.U. reconstruido, de modo que el análisis de la hoja "01" siga cuadrando
  Y el lector no reasigna "SIROC" a "INDIRECTOS" ni a otro tipo
```

### CA-7 `[M]` · Rechazo · Análisis sin código · `HDU-001 esc. 7`

```gherkin
Escenario: Un análisis sin código queda sin asociar y se reporta
  Dado la hoja "NICHO DE TOMAS DE GAS " de ENITI y las 20 hojas de Union Square, todas con la celda de código vacía
  Cuando el lector asocia cada análisis con su concepto
  Entonces los 21 análisis se conservan con sus insumos y cargos, sin concepto asociado
  Y el lector reporta un hallazgo por cada uno con hoja, fila 12, columna "C" y la causa "análisis sin código"
  Y no asocia por el nombre de la hoja ni por la descripción del concepto, aunque la hoja se llame "MURO STD-635-STD"
```

### CA-8 `[M]` · Rechazo · Código en dos hojas · `HDU-001 esc. 9`

```gherkin
Escenario: Un código en dos hojas conserva ambas y reporta la ambigüedad
  Dado el archivo de ENITI, donde los códigos "620014", "620045" y "620050" aparecen cada uno en dos hojas
  Cuando el lector asocia cada análisis con su concepto
  Entonces conserva los seis análisis, cada uno con su propio contenido
  Y reporta un hallazgo por cada hoja de esos códigos, con hoja, fila 12, columna "C", el código y el nombre de la otra hoja
  Y no elige una hoja por encima de la otra ni las fusiona
```

### CA-9 `[M]` · Rechazo · P.U. de la cabecera con `#REF!` · `HDU-001 esc. 6`

```gherkin
Escenario: Una cabecera con fórmula rota se reporta y el pie sigue siendo la referencia
  Dado las hojas "14", "15", "16", "18" y "19" de ENITI, con "#REF!" en la celda "P.U:" de la fila 15
  Cuando el lector las analiza
  Entonces reporta un hallazgo por hoja con hoja, fila 15, columna "C" y valor original "#REF!"
  Y el P.U. del archivo contra el que se verifica es el del pie "PRECIO UNITARIO", que sí es numérico
  Y el análisis se conserva y no se sustituye el "#REF!" por cero
```

### CA-10 `[M]` · Rechazo · El P.U. reconstruido no cuadra · `HDU-001 esc. 6`

```gherkin
Escenario: Una diferencia mayor a un centavo se reporta como error bloqueante
  Dado un libro sintético con una hoja de APU cuyo pie "PRECIO UNITARIO" vale 641.38 mientras sus líneas reconstruyen 641.3608310977561
  Cuando el lector verifica el P.U.
  Entonces reporta un hallazgo bloqueante con hoja, fila del pie, columna "G", el P.U. del archivo, el reconstruido y la diferencia
  Y una diferencia de exactamente 0.01 cuadra y no genera hallazgo
  Y una diferencia de 0.0100001 sí lo genera
  Y el lector no corrige el P.U. del archivo ni el reconstruido
  Y las 44 hojas de APU de los dos archivos reales cuadran sin hallazgo de este tipo
```

### CA-11 `[M]` · Rechazo · Valores que no se pueden interpretar · `HDU-001 esc. 6`

```gherkin
Escenario: Un renglón de insumo con celdas rotas se reporta y no se convierte en cero
  Dado una hoja sintética donde un material trae rendimiento "#REF!", otro trae costo "veinte" y un tercero trae rendimiento -1
  Cuando el lector la analiza
  Entonces reporta un hallazgo por cada celda con hoja, fila, columna "F" o "E" y valor original
  Y el insumo se conserva con ese valor sin dato, nunca en cero
  Y cuando el rendimiento está vacío reporta rendimiento ausente en la columna "F"
  Y si algún valor necesario para reconstruir el P.U. no se puede leer, reporta que el P.U. no es verificable y no lo da por cuadrado
```

### CA-12 `[M]` · Insumos por crear, por descripción normalizada · `HDU-001 esc. 10`

```gherkin
Escenario: Solo se proponen los insumos que no existen, comparados por descripción normalizada
  Dado el archivo de ENITI y una lista de claves existentes que contiene "CANAL 635X3.05 CAL.26"
  Cuando el lector arma los insumos por crear
  Entonces "CANAL 635X3.05 CAL.26" no aparece, aunque en el archivo venga escrito en minúsculas o con espacios al final o repetidos entre palabras
  Y con una lista vacía devuelve 29 insumos por crear para ENITI, 26 de tipo MATERIAL y 3 de tipo MANO_OBRA, y 23 para Union Square, 21 y 2
  Y la clave es la descripción recortada, en mayúsculas y con los espacios interiores colapsados
  Y cada insumo trae la descripción leída recortada, la unidad normalizada, el tipo que determina su bloque y creado_en_importacion verdadero
  Y el mismo insumo en varias hojas aparece una sola vez
  Y el lector no escribe nada ni abre conexión: la lista de claves existentes es un parámetro
```

### CA-13 `[M]` · Rechazo · Unidad de insumo fuera del catálogo · invariante 27

```gherkin
Escenario: Un insumo con una unidad que el esquema no admite no se propone
  Dado una hoja sintética donde un material trae la unidad "LT" y otro la unidad "M²"
  Cuando el lector arma los insumos por crear
  Entonces ninguno de los dos aparece como insumo por crear
  Y el lector reporta un hallazgo por cada uno con hoja, fila, columna "D" y el valor original
  Y el insumo se conserva dentro del análisis con la unidad sin normalizar
  Y una unidad como "CAJA " o "pza" sí se normaliza y no genera hallazgo
```

### CA-14 `[M]` · Rechazo · El mismo insumo con dos unidades · invariante 27

```gherkin
Escenario: Una descripción con unidades distintas no se resuelve en silencio
  Dado dos hojas sintéticas que traen "TORNILLO S-1", una con unidad "PZA" y otra con "CAJA"
  Cuando el lector arma los insumos por crear
  Entonces reporta un hallazgo de unidad en conflicto con las dos hojas, filas y unidades
  Y no elige una de las dos unidades ni propone el insumo con la primera que encontró
  Y lo mismo ocurre cuando la unidad leída difiere de la del insumo existente que reciba el lector
```

### CA-15 `[M]` · El resultado es un valor en memoria con cifras exactas · regla 1

```gherkin
Escenario: Leer no escribe y las cifras salen exactas
  Dado una base de datos migrada con sus tablas de APU vacías
  Cuando el lector analiza cualquiera de los dos archivos reales
  Entonces el lector no recibe ni abre una conexión a la base
  Y apu, apu_insumo, apu_cargo e insumo siguen sin filas nuevas
  Y todo costo, rendimiento, cargo, porcentaje, base e importe del resultado es un Decimal y ninguno es float
  Y la conversión del número del Excel a Decimal es determinista: el mismo archivo produce las mismas cifras en cada lectura
  Y el rendimiento 0.3278 se lee como 0.3278 exacto, sin ruido de coma flotante
```

### CA-16 `[S]` · Totales por análisis · `HDU-001 esc. 5`

```gherkin
Escenario: El lector entrega los totales reconstruidos de cada análisis
  Dado el análisis "MURO STD-635-STD "
  Cuando el lector entrega los totales
  Entonces informa material 201.669152, mano de obra 286.0707317073171, costo directo 487.7398837073171 y P.U. reconstruido 641.3608310977561
  Y cada total se suma de las líneas leídas con precisión completa, sin redondeo intermedio
  Y un total que depende de un valor ilegible es "no calculable" y nunca cero
```

### CA-R1 `[M]` · Regresión · Fronteras y pureza del dominio · reglas 2 y 3

```gherkin
Escenario: El lector no cruza ninguna frontera
  Dado el lector incorporado al módulo presupuesto
  Cuando corre "lint-imports"
  Entonces pasa
  Y "dominio/" no importa "openpyxl" ni ningún paquete de terceros
  Y ningún otro módulo importa el lector por fuera de "cimenta.presupuesto.interfaz"
```

### CA-R2 `[M]` · Regresión · Dinero sin flotantes · regla 1

```gherkin
Escenario: Ninguna firma nueva usa float
  Dado el código nuevo de "dominio/" y de "tipos_base/"
  Cuando corre "python -m herramientas.verificar_float"
  Entonces pasa
```

### CA-R3 `[M]` · Regresión · El lector de catálogo sigue igual · ADR-033

```gherkin
Escenario: Reutilizar la apertura del libro no cambia el catálogo
  Dado el lector de APU incorporado
  Cuando corren las pruebas de TKT-013 contra los dos archivos reales y contra el libro sintético
  Entonces siguen en verde con las mismas cifras: 5,028 conceptos en ENITI y 4,281 en Union Square
  Y "leer_catalogo" conserva su firma
```

## Definition of Ready — INVEST

| | Criterio | ¿Pasa? | Nota |
|---|---|---|---|
| **I** | Independiente en valor y despliegue | Sí, con reserva | Es un lector probado, y su valor llega con TKT-018. En código depende solo de TKT-013b, ya fusionado |
| **N** | Describe el qué, no impone el cómo | Sí | Cómo se abre el libro (una vez o dos), cómo se compara con tolerancia y qué tipo numérico lleva el rendimiento se dejan al diseño |
| **V** | Un rol del PRD obtiene algo que hoy no tiene | Sí, con reserva | El Director de Proyectos ve el análisis leído y los cuadres rotos solo cuando esté la pantalla de TKT-018 |
| **E** | Estimable sin investigar antes | Sí | Los dos archivos reales se midieron para esta spec |
| **S** | Cabe en una sesión sin romper contexto | Sí, con reserva | Talla M, 16 criterios. El diseño debe vigilar el tope de unas 400 líneas por cambio; el recorte natural es `S1` y, si no basta, partir como en TKT-013 |
| **T** | Sus criterios se pueden ejecutar | Sí | Contra los archivos reales en local; en CI, con el libro sintético |

Cero fallos; tres reservas (I, V, S). Pasa.

## Definition of Done

La de un ticket de funcionalidad, de [`sdd/metodologia.md` §8](../../metodologia.md#8--definition-of-done-por-tipo), más la de HDU-001.

- [ ] Ningún Should ni Could implementado sin su criterio en esta spec
- [ ] Cada Must tiene al menos un criterio `[M]` con test que lo nombra: `test_hdu001_esc05_…`, `test_hdu001_esc06_…`, `test_hdu001_esc07_…`, `test_hdu001_esc09_…` y `test_hdu001_esc10_…`
- [ ] Contra los dos archivos reales, no solo contra archivos sintéticos (DoD de HDU-001)
- [ ] `uv run ruff check .`, `uv run mypy .`, `uv run lint-imports`, `uv run python -m herramientas.verificar_float` y `uv run pytest` en verde
- [ ] Documentación afectada actualizada en el mismo cambio: la regla de clave de insumo de `docs/05-tickets-trabajo.md` (TKT-010, que dice «la clave del importador es el `codigo` recortado y en mayúsculas»), el ADR-032 y el texto del criterio «Da de alta los insumos que no existan» de TKT-014; `python tools/verificar_docs.py` en verde

## Preguntas abiertas y supuestos

**Decisiones de la persona dueña, 2026-11-02** (tomadas en el intake de esta spec):

1. **Clave de insumo.** Las hojas de APU no traen código por insumo, así que la decisión A2 no se puede aplicar. La clave es la descripción recortada, en mayúsculas y con los espacios interiores colapsados. Sustituye a A2 para el importador. Queda como `(asumido)` que esto basta para no duplicar insumos.
2. **Asociación.** Solo por el código de la hoja. Sin código se reporta; un código en dos hojas se reporta y no se elige. No se asocia por nombre de hoja ni por descripción.
3. **Alta de insumos.** El lector es en memoria. TKT-014 devuelve los insumos «por crear» y los escribe TKT-017 al confirmar.
4. **Tolerancia.** ±0.01 absoluta, en precisión completa, con hallazgo crudo bloqueante.
5. **Rendimiento de la mano de obra.** El lector lee rendimiento y cargo tal como vienen y lo deja abierto (`PA-T6`).
6. **`SIROC`.** Hallazgo crudo y ticket futuro para ampliar el CHECK; no se amplía aquí.

| # | Supuesto o pregunta | Impacto si es falso | Estado |
|---|---|---|---|
| **PA-T1** | La descripción normalizada identifica un insumo `(asumido)`. Un error tipográfico del Excel (`TONILLO MINI P/BROCA`) produce un insumo distinto del correcto, y la semilla `TBR-001` a `TBR-027` no coincidirá con casi ningún insumo real: casi todos saldrán «por crear». Hay que revisar la previsualización | Insumos duplicados con nombres casi iguales | `(asumido)`; lo vigila la previsualización de TKT-018 |
| **PA-T2** | **Los códigos repetidos del catálogo (`PA-T1` de TKT-013).** El análisis se liga al código, y el catálogo repite cada código por área (162 filas de `620001` en ENITI). El modelo dice «un APU por concepto». El lector asocia un análisis a todas las filas con su código y no resuelve la cardinalidad | Alto en TKT-015 y TKT-017; nulo aquí | Escalada a la persona dueña desde TKT-013 |
| **PA-T3** | Los análisis de Union Square no se pueden asociar con ningún concepto: sus 20 hojas no traen código. El caso de prueba de `MURO STD-635-STD` se lee y se verifica, pero queda sin asociar. Quién da el código a esas hojas (el Excel corregido o un mapa de la Dirección) | Union Square no se puede confirmar con esta regla | Abierta; a la persona dueña y a TKT-015 |
| **PA-T4** | El código del análisis y el del catálogo se comparan recortados y en mayúsculas, igual que la regla de clave del importador `(asumido)` | Un `620040-a` no empata con `620040-A` | `(asumido)` |
| **PA-T5** | El P.U. del archivo contra el que se verifica es el del pie «PRECIO UNITARIO», y el de la cabecera, si es legible, se lee pero no se compara `(asumido)`. En 5 hojas de ENITI el de la cabecera es `#REF!` y el del pie no | Un cuadre contra la cabecera pasaría por alto un pie roto | `(asumido)` |
| **PA-T6** | **Semántica del rendimiento de la mano de obra.** El glosario define `cargo = costo × rendimiento`; para la mano de obra el archivo usa `costo ÷ rendimiento`. TKT-016 multiplica `cantidad × rendimiento` para la explosión y daría un resultado equivocado con la mano de obra. La `CUADRILLA DE LIMPIEZA` de Union trae un cargo que no sigue ninguna fórmula y que este ticket no marca | Explosión de mano de obra incorrecta; una cifra rota que pasa en silencio | Abierta; a la persona dueña y a TKT-016 antes de su diseño |
| **PA-T7** | Los rótulos se mapean a los siete tipos por su texto: `HERRAMIENTA MENOR`, `ANDAMIAJE`, `DESPERDICIO`, `INDIRECTOS`, `UTILIDAD`, los que empiezan por `IVA` y los del bloque de viáticos `(asumido)`. El nombre de rol de un renglón de viáticos (`OFICIAL TABLAROQUERO`) se conserva como descripción | Un cargo con otro rótulo sale «desconocido» | `(asumido)` |
| **PA-T8** | El tipo de un insumo sale solo de su bloque: material es `MATERIAL` y mano de obra es `MANO_OBRA`. `HERRAMIENTA` y `CONSUMIBLE` no tienen bloque en el APU `(asumido)` | Un insumo clasificado con otro tipo | `(asumido)` |
| **PA-T9** | `apu.fecha_analisis` y `apu.analista` son `NOT NULL` y los dos archivos los traen en todas las hojas. Una hoja sin ellos se reporta; el lector no los inventa `(asumido)` | Un APU que no se puede materializar | `(asumido)` |
| **PA-T10** | El valor de `±0.01` es un supuesto del lector, no una regla del PRD. `tipos_base` no tiene hoy una comparación con tolerancia ni el producto `Dinero × Rendimiento` (`PA-T11` de TKT-004). Cómo se resuelve es del diseño | Falsos positivos o negativos en el cuadre | Resuelta en el diseño del 2026-11-02: la tolerancia vive en el dominio sobre `Decimal` y el cuadre suma lo leído, sin `Dinero × Rendimiento` |
| **PA-T11** | `SIROC` (1 % en 20 hojas de ENITI) no tiene tipo en el CHECK de `apu_cargo`. Hace falta decidir si es un octavo tipo, un indirecto o se omite. Mientras tanto, se lee y se reporta | ENITI no se puede confirmar | Abierta; ticket futuro |
| **PA-T13** | `insumo.codigo` es `NOT NULL` y `UNIQUE`, y las hojas no traen código. `InsumoPorCrear` no lleva código y TKT-017 lo genera con una regla propia que la persona dueña confirma al definirlo. Decisión del 2026-11-02 (P14) | TKT-017 no puede materializar sin esa regla | Resuelta para TKT-014; **resuelta el 2026-11-05 para TKT-017** (`PA-T17.5`): `insumo.codigo` es la clave normalizada del lector; si el insumo ya existe con la misma unidad y tipo se reutiliza, y si difiere responde `409` `ESTADO_NO_PERMITE_OPERACION` |
| **PA-T12** | `openpyxl` ya es dependencia de TKT-013; este ticket no añade ninguna. No hay servicio externo de pago, cuenta ni clave de API | — | Resuelta |

## Pasada adversarial

Resultado de `abogado-del-diablo` sobre esta spec.

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Crítica | La clave por descripción es la opción que A2 había descartado, y el ticket de TKT-010 y el ADR-032 aún dicen que la clave es el código. Además un error tipográfico duplica insumos y la semilla no empata con los reales | Decisión 1 de la persona dueña, `PA-T1` y la DoD obliga a corregir `docs/05` y el ADR-032 en el mismo cambio. Se añadió `CA-14` para el conflicto de unidad |
| 2 | Alta | El cuadre se hace con las propias cifras del archivo: pasa aunque el cargo de la `CUADRILLA DE LIMPIEZA` sea absurdo, y da una falsa tranquilidad | `PA-T6` lo declara; el cuadre solo verifica la suma. Se aclara en `CA-10` y en Won't que no revisa la fórmula de cada cargo |
| 3 | Alta | El P.U. de referencia es ambiguo: en 5 hojas de ENITI la cabecera es `#REF!` y el pie no | `PA-T5` y `CA-9` lo resuelven con el pie como referencia, marcado `(asumido)` |
| 4 | Alta | «Asocia cada análisis con su concepto» no se puede probar en Union Square, el único archivo con el caso `MURO STD-635-STD`, porque sus hojas no traen código; y en ENITI un código liga a 162 filas | `CA-5`, `CA-7` y `PA-T3` dicen con franqueza qué se puede asociar y qué no; el caso de `MURO STD-635-STD` se prueba como lectura y cuadre, sin asociación |
| 5 | Media | La tolerancia de ±0.01 no tiene respaldo en el PRD y `tipos_base` carece de las operaciones para hacerla | `PA-T10` la marca `(asumido)` y deja al diseño la comparación; `CA-10` fija el borde exacto (0.01 cuadra, 0.0100001 no) |

## Contexto técnico

Siempre al final: el agente lee de arriba abajo, y si esto va primero decide sobre técnica antes de entender el producto.

- **Módulo y capas:** `presupuesto`, en `dominio` (el modelo del análisis leído, la normalización, el mapeo de rótulos y la verificación del P.U., sin importar nada que no sea la biblioteca estándar y `tipos_base`, ADR-021) y en `infraestructura` (donde vive `openpyxl`). Sin api, aplicación ni frontend.
- **Lo que deja TKT-013:** `backend/cimenta/presupuesto/dominio/catalogo.py` y `lectura_catalogo.py` (`normalizar_unidad`, `interpretar_numero`, `letra_de_columna`, `Hallazgo`, `CausaHallazgo`), y `infraestructura/lector_catalogo.py` con `leer_catalogo(contenido: bytes)`, que abre el libro con `read_only=True` y `data_only=True` y convierte el `float` con `Decimal(repr(f))` ([ADR-033](../../../docs/adr/20261102-lectura-posicional-del-catalogo.md)). Hoy `interpretar_numero` no admite `Rendimiento` ni `Porcentaje`, y `tipos_base` no tiene `Dinero × Rendimiento` ni una comparación con tolerancia.
- **Tablas que no se tocan:** `insumo`, `precio_insumo`, `apu`, `apu_insumo` y `apu_cargo` (migración `v0006`). Sus restricciones fijan el vocabulario: `ck_insumo_tipo`, `ck_insumo_unidad`, `ck_apu_cargo_tipo` y `uq_insumo_codigo`. Los importes van en `NUMERIC(14,4)`, los rendimientos en `(18,6)` y los porcentajes en `(9,6)`; el lector conserva precisión completa y `cuantizar()` queda para TKT-017.
- **Interfaz:** sin operaciones en el borrador OpenAPI. La única relacionada es `listar_insumos` (`x-tickets: [TKT-012]`, con el filtro `creado_en_importacion`).
- **Documentos:** [`docs/03-modelo-datos.md`](../../../docs/03-modelo-datos.md) (invariante 27, `apu`, `apu_insumo`, `apu_cargo`), [`docs/04-historias-usuario.md`](../../../docs/04-historias-usuario.md) HDU-001 escenarios 5, 6, 7, 9 y 10, [`docs/glosario.md`](../../../docs/glosario.md) (APU, rendimiento, cargo, jornal) y [ADR-033](../../../docs/adr/20261102-lectura-posicional-del-catalogo.md).
- **Archivos reales:** `D:\Documentos\Miich\Documentos\` (fuera del repositorio). No se copian al repositorio.
- **Dependientes:** TKT-015 clasifica los hallazgos, TKT-016 calcula la explosión con el rendimiento leído y TKT-017 materializa el análisis, los insumos y los cargos.
