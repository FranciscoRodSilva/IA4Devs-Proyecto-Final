# Spec · TKT-013 · Lector del catálogo de conceptos

> [← index](_index.md) | Siguiente: [design →](design.md)

## Contexto y problema

La importación de la línea base (HDU-001) empieza por leer el Excel del catálogo de conceptos. Hoy no existe nada que lo lea: `backend/cimenta/presupuesto/` solo tiene paquetes vacíos y `openpyxl` no es dependencia del proyecto. TKT-013 construye ese lector. Es la primera pieza del análisis (TKT-013 a TKT-015) y bloquea a TKT-014, que lee los análisis de precios unitarios, y por esa vía a TKT-015 a TKT-018.

Lo que se sabe de los archivos reales, medido el 2026-11-02 sobre las copias de `D:\Documentos\Miich\Documentos\`, y que condiciona la especificación:

| | ENITI Torre 5 (`Presupuesto Base Tablaroca Eniti T5 AP 2.xlsx`) | Union Square F2 (`AP-058-25 SEGUNDA ETAPA P.U UNION SQUERE.xlsx`) |
|---|---|---|
| Hojas | 25 | 24 |
| Hoja del catálogo | `CATALOGO`, 5,988 filas | `CATALOGO DE CONCEPTOS`, 4,860 filas |
| Fila de encabezado | 8: `Código · ENCHAPES · Unidad · Cantidad · P.U. · IMPORTE` | 8: `CODIGO · DESCRIPCION COMPLETA · UNIDAD · CANTIDAD · P.U. · IMPORTE · NOTAS` |
| Filas de concepto (con código) | 5,028 | 4,281 |
| Filas sin código | 951 | 571 |
| Códigos distintos | 36 | 31 |
| Código | Número o texto (`620040-A`) | Número |
| Unidades encontradas | `M2`, `ML`, `Pza`, `PZA`, `pza` | `M2`, `Ml`, `Pza` |
| P.U. e importe | Numéricos | `#REF!` en los 4,281 conceptos |

Hallazgos de estructura:

- **La jerarquía no viene por indentación.** Son filas sin código con el nombre en la columna B. El ticket habla de «indentación y filas sin código»; en los dos archivos reales solo existen las segundas. Un nivel, un área y una partida son filas idénticas en forma: se distinguen por su posición respecto de los conceptos que cuelgan de ellas.
- **El encabezado cambia de texto y de mayúsculas** entre archivos, y en ENITI la celda de la descripción dice `ENCHAPES`, no «descripción».
- **Union Square tiene conceptos sin fila de partida.** El área «Pasillos» del nivel 1 (hoja `CATALOGO DE CONCEPTOS`, filas 11 a 16) tiene conceptos colgados directamente del área. El modelo exige que `concepto.partida_id` exista y que `partida` tenga `tipo_partida_id`, así que ese caso no cabe en el modelo tal como está.
- **Hay nombres de partida fuera de los cuatro tipos.** ENITI trae `ENCHAPES Y PINTURAS` como fila de partida (3 veces) y ambos archivos usan `PASILLO` o `PASILLOS` como área.
- **Los códigos se repiten dentro de la misma obra.** El código `620001` aparece en cada departamento. Esto choca con el invariante 13 y con el escenario 9; no lo resuelve este ticket y se escala (ver «Preguntas abiertas»).

## Historia de usuario

**Como** Director de Proyectos
**quiero** que el sistema lea el catálogo de conceptos de mi Excel y reconstruya su jerarquía de obra, nivel, área, partida y concepto
**para** poder revisar lo que se va a importar antes de aceptarlo, sin que nada se escriba todavía en el modelo real.

## Alcance

| Nivel | Ítem |
|---|---|
| **Must** | **M1.** Localizar, sin posiciones fijas, la hoja del catálogo, la fila de encabezado y las columnas de código, descripción, unidad, cantidad, P.U. e importe, de modo que lea tanto el archivo de ENITI como el de Union Square |
| **Must** | **M2.** Reconstruir la jerarquía obra › nivel › área › partida › concepto a partir de las filas sin código y de su posición, y devolver cada concepto ubicado en su nivel, área y partida |
| **Must** | **M3.** Normalizar la unidad de cada concepto contra las ocho unidades del catálogo cerrado (invariante 27), solo por mayúsculas y espacios; conservar el valor original cuando no se reconozca |
| **Must** | **M4.** Devolver el resultado como un valor en memoria, sin escribir en el modelo real ni persistir nada; cantidad, precio unitario e importe como `Decimal`, nunca `float` |
| **Must** | **M5.** Reportar hoja, fila, columna y valor original de cada valor que no pueda interpretar (`#REF!`, texto en una columna numérica, unidad no reconocida, nombre ilegible, concepto sin partida, estructura no localizada), sin clasificarlo en los tipos de `importacion_error` |
| **Must** | **M6.** Probarlo contra los dos archivos reales, además de contra archivos sintéticos para los casos que los reales no traen |
| **Should** | **S1.** Totales de la jerarquía leída —número de niveles, áreas, partidas y conceptos, e importe calculado— para la previsualización del escenario 5 de HDU-001. Un importe sin P.U. legible es «no calculable», nunca cero |
| **Could** | — |
| **Won't** | Leer los análisis de precios unitarios (TKT-014) · clasificar hallazgos en `REF_ROTA`, `UNIDAD_DESCONOCIDA`, `SIN_APU`, `RENDIMIENTO_AUSENTE`, `DUPLICADO` y `SIN_CONCEPTOS` (TKT-015) · detectar códigos duplicados (TKT-015) · persistir la zona de preparación (la decide quien consuma el resultado; este ticket no añade migración) · asociar el nombre de una partida con un `tipo_partida` · inferir el tipo de una partida sin fila de partida · rutas, orquestación y estado de la importación (TKT-018) · confirmar o materializar (TKT-017) · validar el archivo por sus bytes (TKT-059) · pantallas |

## Partición en dos entregas

La persona dueña aprobó el 2026-11-02 partir el ticket en dos entregas con un PR cada una, como TKT-011. El orden de fusión es fijo: **TKT-013a y después TKT-013b**. TKT-013 queda como paraguas, conserva esta spec y el diseño, y se cierra cuando se cierran las dos. TKT-014 pasa a depender de TKT-013b.

| Entrega | Contenido |
|---|---|
| TKT-013a | Dominio puro, sin dependencia nueva ni archivos externos: la lógica de `M1` a `M5` sobre filas en memoria |
| TKT-013b | `openpyxl`, el lector de infraestructura, las pruebas contra los archivos reales (`M6`), la conversión de `float` a `Decimal` de `M4` y el Should `S1` |

Cómo se reparten los criterios:

| Criterio | TKT-013a | TKT-013b |
|---|---|---|
| `CA-1`, `CA-2`, `CA-5`, `CA-7`, `CA-12` | La misma lógica con filas en memoria | Contra los archivos reales y el libro sintético |
| `CA-3`, `CA-4`, `CA-9`, `CA-11` | Filas en memoria que repiten el patrón de corridas, con nombres neutros | Contra los archivos reales |
| `CA-6`, `CA-8`, `CA-10` | Filas en memoria | Libro sintético construido con `openpyxl` |
| `CA-13` | — | Sí |
| `CA-R1`, `CA-R2` | Sí | Sí |
| `CA-R3` | — | Sí |
| Definition of Done, «contra los dos archivos reales» | — | Sí |

## Non-goals

- No escribe en ninguna tabla. No abre sesión de base de datos.
- No decide el estado de la importación: el lector devuelve hallazgos; que la importación quede `CON_ERRORES` lo decide TKT-015.
- No toma partido sobre los códigos repetidos: devuelve todas las apariciones, en el orden del archivo.
- No convierte el nombre de una partida en un `tipo_partida`, ni crea tipos nuevos.
- No acepta archivos que no hayan pasado la validación por bytes del módulo `archivos` (TKT-059, ADR-016 regla 3): el lector no se llama con un archivo sin validar.
- No cambia el modelo de datos, el borrador OpenAPI ni el catálogo de tipos de error.

## Reglas de negocio implicadas

Ninguna `RN-xx` gobierna la lectura. El requisito es F1.1 del PRD: importar el catálogo respetando la jerarquía obra › nivel › área › partida › concepto.

| Regla | Qué exige | Dónde está |
|---|---|---|
| `RN-01` | Nada se escribe en el modelo real antes de confirmar; lo que se lee no toca la línea base. Aquí solo se respeta por omisión: el lector no escribe | PRD §8 — `docs/01-descripcion-producto.md` |
| Regla 1 de `CLAUDE.md` | El dinero nunca es flotante; las cifras del Excel llegan como `float` y salen como `Decimal` | `CLAUDE.md` |

El escenario de rechazo no cuelga de una `RN` sino de la regla 1 de `CLAUDE.md` y de HDU-001 esc. 6 y 8: el valor que no se puede interpretar se reporta con su ubicación y no se sustituye por un valor inventado.

## Invariantes que deben sobrevivir al cambio

El ticket no modifica comportamiento existente, pero añade una dependencia (`openpyxl`) y código nuevo en `presupuesto`. Estas garantías ya vigentes no pueden romperse.

| Invariante | Qué protege | Criterio de regresión |
|---|---|---|
| Regla 2 de `CLAUDE.md` | `dominio/` no importa `openpyxl` ni ningún paquete de terceros | `CA-R1` |
| Regla 1 de `CLAUDE.md` | Ningún `float` en firmas de `dominio/` ni de `tipos_base/` | `CA-R2` |
| Regla 3 de `CLAUDE.md` | Ningún módulo cruza la frontera de otro por su infraestructura | `CA-R1` |
| Cadena de dependencias | `pip-audit` sigue limpio con la dependencia nueva | `CA-R3` |

## Criterios de aceptación

Las cifras salen de la medición del 2026-11-02 (ver «Contexto y problema») y el diseño las confirma en su fila de arranque. Los archivos reales no se versionan; la pregunta `PA-T3` fija cómo se ejecutan en CI.

### CA-1 `[M]` · Lee el catálogo de ENITI · `HDU-001 esc. 5`

```gherkin
Escenario: El lector reconoce el catálogo de ENITI Torre 5
  Dado el archivo "Presupuesto Base Tablaroca Eniti T5 AP 2.xlsx"
  Cuando el lector lo analiza
  Entonces localiza la hoja "CATALOGO" y su encabezado en la fila 8
  Y devuelve 5,028 conceptos en el orden del archivo
  Y el primer concepto es el código "620001" de la fila 13, unidad "M2", cantidad 16.089000000000002 (repr del float del archivo), precio unitario 668.69
  Y el código "620040-A" de la fila 29 conserva su sufijo como texto
  Y no abre ni interpreta las otras 24 hojas
```

### CA-2 `[M]` · Lee el catálogo de Union Square · `HDU-001 esc. 5`

```gherkin
Escenario: El lector reconoce el catálogo de Union Square F2
  Dado el archivo "AP-058-25 SEGUNDA ETAPA P.U UNION SQUERE.xlsx"
  Cuando el lector lo analiza
  Entonces localiza la hoja "CATALOGO DE CONCEPTOS" y su encabezado en la fila 8
  Y devuelve 4,281 conceptos en el orden del archivo
  Y el primer concepto es el código "620012" de la fila 12
  Y las cantidades de las columnas enteras y decimales llegan como Decimal
```

### CA-3 `[M]` · Reconstruye la jerarquía por posición · `HDU-001 esc. 5`

```gherkin
Escenario: Nivel, área y partida salen de las filas sin código
  Dado el catálogo de ENITI
  Cuando el lector reconstruye la jerarquía
  Entonces el concepto "620001" de la fila 13 queda en la ruta
    "ACABADOS EN MUROS Y PLAFONES" › "NIVEL 1" › "LOBBY Y PASILLO" › "MUROS"
  Y el concepto "620040-A" de la fila 29 queda en
    "NIVEL 1" › "CUBO DE ESCALERAS" › "ENCHAPES"
  Y el concepto "620001" de la fila 32 queda en
    "NIVEL 1" › "DEPARTAMENTO 101 TIPO E" › "MUROS"
  Y cada fila sin código es un nodo de nivel, área o partida, nunca un concepto
  Y el nombre de cada nodo se conserva tal como está escrito, sin mapearlo a un tipo de partida
```

### CA-4 `[M]` · Segunda estructura y variantes de nombre · `HDU-001 esc. 5`

```gherkin
Escenario: La misma jerarquía se reconstruye en el archivo de Union Square
  Dado el catálogo de Union Square, donde el nivel se llama "Nivel 1" y las partidas "Muros" y "Plafones y cajillos"
  Cuando el lector reconstruye la jerarquía
  Entonces el concepto "620001" de la fila 19 queda en
    "Nivel 1" › "DPTO. 111 TIPO  3R" › "Muros"
  Y el lector no depende de que el nombre esté en mayúsculas ni de que se llame "NIVEL"
```

### CA-5 `[M]` · Unidades normalizadas contra el catálogo · `HDU-001 esc. 8`

```gherkin
Escenario: Las variantes de mayúsculas se normalizan
  Dado los catálogos reales, con unidades escritas "Pza", "pza", "PZA" y "Ml"
  Cuando el lector normaliza las unidades
  Entonces "Pza", "pza" y "PZA" quedan como "PZA"
  Y "Ml" queda como "ML"
  Y ENITI suma 1,763 conceptos "M2", 2,079 "ML" y 1,186 "PZA"
  Y Union Square suma 1,237 conceptos "M2", 2,189 "ML" y 855 "PZA"
```

### CA-6 `[M]` · Rechazo · Unidad que no está en el catálogo · `HDU-001 esc. 8`

```gherkin
Escenario: Una unidad desconocida se reporta con su valor original
  Dado una hoja sintética donde un concepto trae la unidad "M2." y otro "M²"
  Cuando el lector la analiza
  Entonces ambos conceptos se conservan en la jerarquía con la unidad sin normalizar
  Y el lector reporta un hallazgo por cada uno con hoja, fila, columna "C" y el valor original "M2." o "M²"
  Y no adivina la unidad ni la sustituye por "M2"
  Y espacios al inicio o al final, como " m2 ", sí se normalizan a "M2" y no generan hallazgo
```

### CA-7 `[M]` · Rechazo · Celdas con `#REF!` · `HDU-001 esc. 6`

```gherkin
Escenario: Las celdas de fórmula rota se reportan por fila y columna
  Dado el catálogo de Union Square, con "#REF!" en el P.U. y el importe de sus 4,281 conceptos
  Cuando el lector lo analiza
  Entonces reporta 8,562 hallazgos de concepto: uno por el P.U. (columna "E") y otro por el importe (columna "F") de cada concepto
  Y el hallazgo de la fila 13 indica hoja "CATALOGO DE CONCEPTOS", fila 13, columna "E" y valor original "#REF!"
  Y los 4,281 conceptos se conservan en la jerarquía, con su cantidad intacta y el P.U. y el importe sin valor
  Y el lector no sustituye el "#REF!" por cero
```

### CA-8 `[M]` · Rechazo · Valores que no son número · `HDU-001 esc. 6`

```gherkin
Escenario: Una columna numérica con texto se reporta y no se convierte en cero
  Dado una hoja sintética donde la cantidad de un concepto es "diez" y su P.U. es "$ 668,69"
  Cuando el lector la analiza
  Entonces reporta un hallazgo en la columna "D" con el valor original "diez" y otro en la columna "E" con "$ 668,69"
  Y la cantidad y el P.U. de ese concepto quedan sin valor, nunca en cero
  Y el concepto sigue en la jerarquía
```

### CA-9 `[M]` · Rechazo · Concepto sin fila de partida · `HDU-001 esc. 5`

```gherkin
Escenario: Un concepto colgado directamente de un área se reporta y no se le inventa partida
  Dado el catálogo de Union Square, donde el área "Pasillos" del nivel 1 tiene los conceptos de las filas 12 a 16 sin fila de partida
  Cuando el lector reconstruye la jerarquía
  Entonces esos conceptos quedan en "Nivel 1" › "Pasillos" sin partida
  Y el lector reporta un hallazgo por cada uno con hoja, fila y la causa "concepto sin partida"
  Y no infiere el tipo de partida por la descripción del concepto
  Y no asigna una partida genérica
```

### CA-10 `[M]` · Rechazo · Estructura no localizada · `HDU-001 esc. 27`

```gherkin
Escenario: Un libro sin hoja de catálogo, sin encabezado o sin conceptos no revienta
  Dado un libro cuyo catálogo no se localiza, o cuya hoja no tiene fila de encabezado, o que tiene encabezado y ninguna fila de concepto
  Cuando el lector lo analiza
  Entonces devuelve un resultado sin conceptos y un hallazgo de estructura con la hoja analizada y la causa
  Y no lanza una excepción que escape del lector
  Y si hay más de una hoja candidata, no elige una al azar: reporta la ambigüedad con los nombres encontrados
```

### CA-11 `[M]` · Una fila sin código y sin nombre no es un nodo · `HDU-001 esc. 5`

```gherkin
Escenario: Las filas vacías y los nombres ilegibles no corrompen la jerarquía
  Dado el catálogo de Union Square, donde 21 filas sin código traen "#REF!" como nombre
  Cuando el lector reconstruye la jerarquía
  Entonces reporta un hallazgo por cada una con hoja, fila, columna "B" y valor original "#REF!"
  Y las filas completamente vacías se ignoran sin generar hallazgo
  Y el nodo de nombre ilegible conserva su posición para que los conceptos de debajo sigan colgando del nodo correcto
```

### CA-12 `[M]` · El resultado no toca el modelo real ni usa `float` · `HDU-001 esc. 5`

```gherkin
Escenario: Leer no escribe y las cifras salen exactas
  Dado una base de datos migrada con sus tablas de catálogo vacías
  Cuando el lector analiza cualquiera de los dos archivos reales
  Entonces el lector no recibe ni abre una conexión a la base
  Y el número de filas de nivel, área, partida y concepto sigue en cero
  Y toda cantidad, precio unitario e importe del resultado es un Decimal y ninguno es float
  Y la conversión del número del Excel a Decimal es determinista: el mismo archivo produce las mismas cifras en cada lectura
```

### CA-13 `[S]` · Totales para la previsualización · `HDU-001 esc. 5`

```gherkin
Escenario: El lector entrega los totales de la jerarquía leída
  Dado el catálogo de ENITI
  Cuando el lector entrega los totales
  Entonces informa los niveles, áreas, partidas y conceptos leídos
  Y el importe de cada concepto es cantidad × precio unitario, con las cifras del archivo
  Y para Union Square, donde ningún P.U. es legible, el importe total es «no calculable» y nunca cero
```

### CA-R1 `[M]` · Regresión · Fronteras y pureza del dominio · reglas 2 y 3

```gherkin
Escenario: La dependencia nueva no cruza ninguna frontera
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

### CA-R3 `[M]` · Regresión · Dependencia auditada

```gherkin
Escenario: openpyxl entra al bloqueo de dependencias sin vulnerabilidades conocidas
  Dado "openpyxl" añadido a "pyproject.toml" y "uv.lock" regenerado
  Cuando corre "pip-audit"
  Entonces no reporta vulnerabilidades en la versión fijada
```

## Definition of Ready — INVEST

| | Criterio | ¿Pasa? | Nota |
|---|---|---|---|
| **I** | Independiente en valor y despliegue | Sí, con reserva | Entrega un lector probado, pero el valor para la persona usuaria llega con TKT-018. Es independiente en código: solo depende de TKT-011b |
| **N** | Describe el qué, no impone el cómo | Sí | El algoritmo de profundidad y la conversión a `Decimal` se dejan al diseño |
| **V** | Un rol del PRD obtiene algo que hoy no tiene | Sí, con reserva | El Director de Proyectos ve su jerarquía leída solo cuando esté la pantalla de TKT-018. Hoy el valor es habilitante |
| **E** | Estimable sin investigar antes | Sí | La investigación de los archivos reales ya se hizo para esta spec |
| **S** | Cabe en una sesión sin romper contexto | Sí, con reserva | Talla M. El diseño debe vigilar el tope de unas 400 líneas por cambio; el recorte natural es el Should |
| **T** | Sus criterios se pueden ejecutar | Sí | Contra los archivos reales en local; en CI, con el fixture sintético (`PA-T3`) |

Cero fallos; tres reservas (I, V, S). Pasa.

## Definition of Done

La de un ticket de funcionalidad, de [`sdd/metodologia.md` §8](../../metodologia.md#8--definition-of-done-por-tipo), más la de HDU-001.

- [ ] Ningún Should ni Could implementado sin su criterio en esta spec
- [ ] Cada Must tiene al menos un criterio `[M]` con test que lo nombra: `test_hdu001_esc05_…`, `test_hdu001_esc06_…`, `test_hdu001_esc08_…`, `test_hdu001_esc27_…`
- [ ] Contra los dos archivos reales, no solo contra archivos sintéticos (DoD de HDU-001)
- [ ] `uv run ruff check .`, `uv run mypy .`, `uv run lint-imports`, `uv run python -m herramientas.verificar_float` y `uv run pytest` en verde
- [ ] `pip-audit` limpio con `openpyxl`
- [ ] Documentación afectada actualizada en el mismo cambio y `python tools/verificar_docs.py` en verde

## Preguntas abiertas y supuestos

| # | Supuesto o pregunta | Impacto si es falso | Estado |
|---|---|---|---|
| **PA-T1** | **Códigos repetidos dentro de la obra.** En los dos archivos cada código de concepto aparece en muchas áreas (ENITI: 36 códigos distintos en 5,028 conceptos; Union Square: 31 en 4,281). El invariante 13 (`UNIQUE (obra_id, codigo)`) y el escenario 9 (`DUPLICADO`) harían imposible confirmar cualquiera de los dos. El wireframe `08-wireframes.md` ya lo muestra como error | **Alto en TKT-015 y TKT-017**, nulo en este ticket: el lector devuelve todas las apariciones | Resuelta el 2026-11-05 por TKT-072: concepto único por obra y concepto de partida por aparición |
| **PA-T2** | El diseño de profundidad por posición es ambiguo cuando un área no tiene partida (Union Square, «Pasillos»): la misma secuencia de filas se lee de dos maneras. El diseño debe resolverlo con una regla determinista y probarla con las filas 9 a 20 del archivo de Union Square | Jerarquía mal armada en silencio | Resuelta el 2026-11-02 en [design.md](design.md), «La regla de profundidad»: cuatro niveles, la primera corrida de filas sin código se alinea a la raíz y las demás a la partida; su límite conocido lo vigila una prueba de oráculo sobre los dos archivos completos |
| **PA-T3** | **Cómo corren en CI las pruebas contra los archivos reales.** Están fuera del repositorio (`Doc de contexto/` en `.gitignore`) y el repositorio es público. La persona dueña dio la ruta local `D:\Documentos\Miich\Documentos` y el 2026-11-02 eligió el tratamiento: ruta por variable de entorno, `skip` explícito y visible si el archivo falta, y fixture sintético con la misma estructura de ambos archivos para CI. Los archivos reales no se copian al repositorio | El criterio contra los archivos reales solo se verifica en la máquina que los tiene; el pipeline lo cubre con el fixture sintético | Resuelta |
| **PA-T4** | Los «dos archivos reales» son ENITI y Union Square (`AP-058-25 SEGUNDA ETAPA P.U UNION SQUERE.xlsx`), como nombra HDU-001. El README lista además `AP-058-25 CATALOGO DE CONCEPTOS TABLAROCA fase 2 union.xlsx`, que esta spec no usa | Un tercer formato sin cubrir | `(asumido)`; pendiente de confirmar |
| **PA-T5** | La hoja del catálogo se localiza por un nombre que empieza por «CATALOGO», sin acentos ni distinción de mayúsculas, y el encabezado por el texto «código» en la primera columna `(asumido)` | Un archivo con otra hoja no se reconoce | `(asumido)`; lo confirma la persona dueña |
| **PA-T6** | La descripción es la columna inmediatamente a la derecha del código, porque en ENITI su celda de encabezado trae `ENCHAPES` en vez de un rótulo `(asumido)` | Descripción tomada de otra columna | `(asumido)` |
| **PA-T7** | Los importes de las filas de grupo (nivel, área, partida) se ignoran: el total se calcula desde los conceptos. Por eso un `#REF!` en el importe de un grupo no es hallazgo, salvo que sea el nombre `(asumido)` | Hallazgos que TKT-015 espera y no recibe | `(asumido)` |
| **PA-T8** | El nombre de partida fuera de los cuatro tipos (`ENCHAPES Y PINTURAS`) y las áreas `PASILLO`/`PASILLOS` se conservan tal cual; quién las asocia con un `tipo_partida`, y qué pasa con las que no tienen ninguno, lo decide TKT-015 o TKT-017 | Concepto que no se puede materializar | Abierta; a TKT-015 y TKT-017 |
| **PA-T9** | Cómo se convierte el `float` de `openpyxl` a `Decimal`: recomendación, usar la representación más corta del número (`16.089000000000002` se lee tal cual) y dejar el redondeo a `cuantizar()` al materializar, para que el lector no pierda información | Cifras con ruido de coma flotante o redondeadas antes de tiempo | Resuelta el 2026-11-02 con la persona dueña: `Decimal(repr(f))`, sin redondear (P2 del diseño) |
| **PA-T10** | Los hallazgos del lector no usan el CHECK de `importacion_error.tipo`: son hallazgos crudos que TKT-015 clasifica. Decisión de la persona dueña del 2026-11-02 | — | Resuelta |
| **PA-T11** | La zona de preparación es un valor en memoria devuelto por el lector, sin tablas nuevas. Decisión de la persona dueña del 2026-11-02, que cierra `PA-T12` de TKT-011. TKT-015 exige conservar las filas válidas entre ejecuciones: si necesita persistencia, la define él | — | Resuelta |
| **PA-T12** | Unidades: se normalizan solo contra las ocho del catálogo, por mayúsculas y espacios. Cualquier otra grafía (`M2.`, `M²`) queda sin normalizar. Decisión de la persona dueña del 2026-11-02 | — | Resuelta |
| **PA-T13** | Un concepto sin partida se reporta y no se infiere ni se completa. Decisión de la persona dueña del 2026-11-02 | — | Resuelta |
| **PA-T14** | `openpyxl` es una biblioteca libre y no hay servicio externo de pago, cuenta ni clave de API. No hay presupuesto que confirmar | — | Resuelta |

## Pasada adversarial

Resultado de `abogado-del-diablo` sobre esta spec.

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Crítica | Los códigos se repiten decenas de veces dentro de cada obra real, y el invariante 13 más el escenario 9 las tratan como `DUPLICADO`. Ninguno de los dos archivos reales se podría confirmar jamás | No cambia este ticket, porque el lector devuelve todas las apariciones. Se registra como `PA-T1` y se escala a la persona dueña; es una colisión entre el modelo y la realidad que afecta a TKT-015 y TKT-017 |
| 2 | Alta | «Reconstruye la jerarquía por indentación» no describe los archivos: no hay indentación y las filas de nivel, área y partida son indistinguibles por forma. La secuencia de «Pasillos» admite dos lecturas | Se reescribió el criterio por posición (CA-3, CA-4), se añadió el contraejemplo real (CA-9) y `PA-T2` obliga al diseño a una regla determinista con prueba sobre las filas 9 a 20 |
| 3 | Alta | Los criterios contra los archivos reales no son verificables si el archivo no está en el pipeline, y el repositorio es público | `PA-T3` con recomendación; los casos que los reales no traen (`M2.`, texto en número, libro vacío) tienen su criterio sintético (CA-6, CA-8, CA-10) |
| 4 | Media | Las cifras (5,028 y 4,281 conceptos) las midió esta spec con un script ad hoc sobre las copias de hoy; si el archivo cambia, el criterio falla sin que el lector tenga defecto | Se citan con fecha y procedencia, y el diseño las reconfirma en su fila de arranque |
| 5 | Media | Se asume que «los dos archivos reales» son ENITI y Union Square, y el README nombra un tercero. Un tercer formato podría romper las reglas de localización | `PA-T4` `(asumido)`; `PA-T5` y `PA-T6` marcan como `(asumido)` las reglas de localización de hoja, encabezado y descripción |

## Contexto técnico

Siempre al final: el agente lee de arriba abajo, y si esto va primero decide sobre técnica antes de entender el producto.

- **Módulo y capas:** `presupuesto`, en `infraestructura` (donde vive `openpyxl`) y, si el diseño lo propone, `dominio` para la jerarquía y las reglas de normalización de unidad, sin importar nada que no sea la biblioteca estándar y `tipos_base` (ADR-021).
- **Biblioteca:** `openpyxl` en modo `read_only=True` y `data_only=True`, según [`docs/06-stack-tecnologico.md`](../../../docs/06-stack-tecnologico.md): con `data_only` un `#REF!` llega como la cadena `#REF!` y no como `None`. No es dependencia todavía y entra a `backend/pyproject.toml` y `uv.lock`.
- **Entrada del lector:** el archivo ya validado por TKT-059. El documento no fija si el lector recibe bytes, un flujo o una ruta: es decisión de diseño.
- **Interfaz:** sin operaciones en el borrador OpenAPI. Las rutas de importación son de TKT-018.
- **Tablas relacionadas que no se tocan:** `nivel`, `area`, `partida`, `concepto` (0006), `importacion` e `importacion_error` (0007). Los hallazgos se parecen a `importacion_error` (hoja, fila, columna, valor original) sin usar su CHECK de `tipo`.
- **Documentos:** [`docs/03-modelo-datos.md`](../../../docs/03-modelo-datos.md) §11 (importación) y el invariante 27, [`docs/04-historias-usuario.md`](../../../docs/04-historias-usuario.md) HDU-001 escenarios 5, 6, 8 y 27, [`docs/glosario.md`](../../../docs/glosario.md) (nivel, área, partida, concepto).
- **Archivos reales:** `D:\Documentos\Miich\Documentos\` (fuera del repositorio). No se copian al repositorio ni se citan sus datos de cliente más allá de lo necesario para los criterios.
