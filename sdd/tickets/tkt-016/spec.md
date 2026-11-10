# Spec · TKT-016 · Cálculo de la explosión por tipo de partida

> [← index](_index.md) | Siguiente: `design.md` (lo escribe `/sdd-disenar`)

## Contexto y problema

La importación de la línea base (HDU-001) ya lee en memoria el catálogo de conceptos (TKT-013) y los análisis de precio unitario (TKT-014b). Lo que nadie hace todavía es **convertir esa lectura en lo que el control presupuestal necesita**: cuánto de cada material requiere la obra entera por tipo de partida, con qué rendimiento se presupuestó y cuánto vale cada tipo de partida a precio de venta y sin utilidad ni indirectos. Sin ese cálculo, TKT-017 no tiene qué copiar al congelar (HDU-001 esc. 14), Dirección no ve el importe sugerido al capturar su tope (esc. 15) y `RN-03` no tiene cantidad presupuestada contra la cual evaluar el volumen de una requisición.

TKT-016 construye ese cálculo como **una regla pura del dominio de `presupuesto`**: recibe los conceptos de una obra, cada uno ya asignado a su tipo de partida y con su análisis de precio unitario asociado, y devuelve la explosión agregada y los importes por tipo de partida, o un rechazo con todas sus causas. No persiste, no expone ruta y no decide a qué tipo de partida pertenece un concepto.

Cuatro hechos medidos por `analista-dominio` el 2026-11-03 condicionan la especificación:

- **No hay mapeo del nombre de una partida a un `tipo_partida`.** El concepto leído solo trae el nombre del nodo partida (`ruta.partida.nombre`); la tabla `tipo_partida` tiene cuatro filas sembradas, y nada asocia una cosa con la otra (`PA-T8` de TKT-013, abierta). La persona dueña decidió el 2026-11-03 que este ticket **recibe el tipo como dato de entrada**.
- **El esquema guarda un solo rendimiento y un solo costo por tipo de partida e insumo** (`explosion_presupuesto`, unicidad `(linea_base_id, tipo_partida_id, insumo_id)`), pero el mismo insumo aparece en varios análisis del mismo tipo con rendimientos y costos distintos. La persona dueña decidió el 2026-11-03 guardar el **promedio ponderado**.
- **Ningún documento da la fórmula del importe sugerido.** El glosario, el modelo de datos, HDU-001 esc. 15, el boceto y el OpenAPI dicen «quitando utilidad e indirectos» sin más. La persona dueña fijó la fórmula el 2026-11-03 (ver `M2`).
- **El oráculo del ticket no se puede reproducir en CI.** La cifra de 27 insumos y $2,755,187.21 viene del archivo `AP-058-25 EXPLOSION DE INSUMOS`, que no está en el repositorio; además, las hojas de análisis de Union Square no se asocian a ningún concepto (0 de 20 con código, `PA-T3` de TKT-014) y traen 23 insumos distintos, no 27. La persona dueña decidió el 2026-11-03 probar en CI con un libro sintético de resultado conocido y dejar la reconciliación real como prueba con `skip` explícito.

## Historia de usuario

**Como** Director de Proyectos
**quiero** que el sistema calcule, a partir del catálogo y de los análisis de precio unitario de mi obra, cuánto de cada material necesita cada tipo de partida en toda la obra y cuánto vale ese tipo de partida sin utilidad ni indirectos
**para** que la línea base que congele lleve la cantidad presupuestada y el rendimiento de cada insumo, y Dirección tenga una referencia al capturar el presupuesto de control.

## Alcance

| Nivel | Ítem |
|---|---|
| **Must** | **M1.** Una regla pura en `presupuesto/dominio/` que, para una obra, recibe sus conceptos —cada uno con su tipo de partida, su cantidad y su análisis de precio unitario asociado— y devuelve **una fila por tipo de partida e insumo de tipo `MATERIAL`**, agregada sobre **toda la obra** (`PA-01`): `cantidad_presupuestada = Σ cantidad_concepto × rendimiento`; `rendimiento_congelado = cantidad_presupuestada / Σ cantidad_concepto` de los conceptos que usan ese insumo; `costo_unitario = Σ (cantidad_concepto × rendimiento × costo_unitario) / cantidad_presupuestada`; `importe = cantidad_presupuestada × costo_unitario`. El insumo se identifica por su clave normalizada ([ADR-035](../../../docs/adr/20261103-clave-de-insumo-y-lectura-de-apu.md)) y el costo sale del análisis leído, no de `precio_insumo` |
| **Must** | **M2.** Por cada tipo de partida, el **importe de venta** `Σ cantidad_concepto × precio_unitario` y el **importe sugerido** `Σ cantidad_concepto × (precio_unitario − cargo UTILIDAD − cargo INDIRECTOS)`, con el precio unitario y los importes de esos cargos tomados **del análisis** del concepto; el precio unitario del catálogo no interviene. El IVA y los demás cargos no se restan. El sugerido viaja marcado como sugerencia y nunca como tope de control (`PA-03`) |
| **Must** | **M3.** Precisión completa en todo el cálculo, sin redondeo intermedio. Solo la salida se lleva a la escala de su columna con `cuantizar()`, que usa `ROUND_HALF_UP`: la persona dueña confirmó ese modo el 2026-11-03 y con ello cierra `PA-23` |
| **Must** | **M4.** Rechazo **todo o nada**: si un solo concepto o insumo no se puede calcular, no se devuelve explosión alguna, sino un rechazo que enumera **todas** las causas —no solo la primera—, cada una con su causa, código de concepto, fila y, si aplica, clave de insumo. Causas: concepto sin tipo de partida, sin análisis asociado, con cantidad ausente o menor o igual que cero, o cuyo análisis no tiene precio unitario; análisis sin cargo `UTILIDAD` o sin cargo `INDIRECTOS`, o con alguno de ellos sin importe; insumo `MATERIAL` sin costo unitario, o con rendimiento ausente o menor o igual que cero; una misma clave de insumo con dos unidades distintas; importe sugerido negativo de un tipo de partida (invariante 8) |
| **Must** | **M5.** Pruebas con un libro sintético de resultado calculado a mano que corre en CI, y una prueba de reconciliación contra el archivo real `AP-058-25` que se omite con `skip` explícito cuando su variable de entorno no está definida |
| **Should** | — |
| **Could** | — |
| **Won't** | La ruta `GET /lineas-base/{linea_base_id}/explosion`, su caso de uso y la persistencia en `explosion_presupuesto` y `presupuesto_control` (TKT-017, dueño de la ruta) · asociar el nombre de una partida con un `tipo_partida` (`PA-T8`) · insumos de mano de obra y el sentido de su rendimiento (`PA-T6` de TKT-014) · capturar el importe tope de Dirección (TKT-017) · leer costos de `precio_insumo` · corregir el borrador OpenAPI (hallazgos para TKT-017) · el rendimiento observado de `RN-24` (v1.1) |

## Non-goals

- No congela nada ni escribe en ninguna tabla: solo calcula en memoria.
- No expone ruta ni caso de uso. La ruta de la explosión es de TKT-017 aunque el borrador OpenAPI cite también a este ticket.
- No decide a qué tipo de partida pertenece un concepto ni interpreta el nombre de la partida.
- No incluye la mano de obra en la explosión.
- No traduce el rechazo al contrato de error: no hay endpoint. Lo traduce el caso de uso de TKT-017.
- No vuelve a validar lo que ya valida TKT-015 (`SIN_APU`, `RENDIMIENTO_AUSENTE`, `REF_ROTA`): el rechazo de `M4` es la defensa del cálculo cuando recibe datos que no puede usar, no un segundo reporte de importación.

## Reglas de negocio implicadas

| Regla | Qué exige | Dónde está |
|---|---|---|
| `RN-24` | La línea base conserva el rendimiento congelado; el observado vive aparte y ninguno sobrescribe al otro. Este ticket produce el `rendimiento_congelado` y no conoce el observado | PRD §8 — [`docs/01-descripcion-producto.md`](../../../docs/01-descripcion-producto.md) |
| `PA-01` | El presupuesto de compras se controla por tipo de partida en toda la obra, no por ubicación | PRD, supuestos |
| `PA-03` | El presupuesto de control se captura; el derivado solo se muestra como sugerencia | PRD, supuestos; F1.5 |
| `PA-23` | Modo de redondeo de los importes. Cerrado el 2026-11-03: `ROUND_HALF_UP` | PRD, supuestos |
| `RN-03` (consumidor) | Evalúa volumen contra la cantidad presupuestada de cada insumo en la explosión. Este ticket no la implementa; produce su dato | PRD §8 |

## Invariantes que deben sobrevivir al cambio

El ticket no modifica nada que ya funcione: añade una regla nueva al dominio. Estos invariantes los toca porque produce los datos que TKT-017 escribirá.

| Invariante | Qué protege | Criterio de regresión |
|---|---|---|
| 8 de [modelo de datos §13](../../../docs/03-modelo-datos.md) | Importes, cantidades y rendimientos no negativos en `explosion_presupuesto` y `presupuesto_control` | `CA-7` |
| 19 de modelo de datos §13 | El rendimiento congelado nunca se sobrescribe con el observado | `CA-9` |
| Unicidad `(linea_base_id, tipo_partida_id, insumo_id)` | Una sola fila por tipo de partida e insumo | `CA-1` |
| Reglas 1 y 2 de `CLAUDE.md` | Dinero sin `float`; `dominio/` sin dependencias externas | `CA-R1` |
| Lectura de TKT-013 y TKT-014b | Lo que devuelven los lectores no cambia | `CA-R2` |

## Criterios de aceptación

Los nombres de insumo y las cifras de los ejemplos son ilustrativos; el diseño fija el libro sintético con sus valores exactos. Ningún criterio expone una ruta, así que ninguno responde un `tipo` del contrato de error: el rechazo es un resultado de dominio que TKT-017 traducirá.

### CA-1 `[M]` · Agregación por tipo de partida en toda la obra · `PA-01` · `HDU-001 esc. 14`

```gherkin
Escenario: el mismo insumo en dos áreas y dos conceptos del mismo tipo da una sola fila
  Dado una obra con dos conceptos del tipo de partida MUROS en áreas distintas
    | codigo  | area   | cantidad | insumo PANEL rendimiento | costo PANEL |
    | MURO-A  | Área 1 | 100      | 1.05                     | 80.00       |
    | MURO-B  | Área 2 | 200      | 1.10                     | 85.00       |
  Cuando se calcula la explosión
  Entonces hay exactamente una fila para (MUROS, PANEL)
  Y su cantidad presupuestada es 100 × 1.05 + 200 × 1.10 = 325
  Y no hay ninguna fila por área ni por nivel
```

### CA-2 `[M]` · Rendimiento y costo ponderados · `RN-24` · `HDU-001 esc. 14`

```gherkin
Escenario: el rendimiento congelado y el costo son promedios ponderados exactos
  Dado los conceptos de CA-1
  Cuando se calcula la explosión
  Entonces el rendimiento congelado de (MUROS, PANEL) es 325 / 300
  Y el costo unitario es (105 × 80.00 + 220 × 85.00) / 325
  Y el importe de la fila es 105 × 80.00 + 220 × 85.00 = 27100.00
  Y rendimiento congelado × Σ cantidad de los conceptos reproduce la cantidad presupuestada sin diferencia
```

### CA-3 `[M]` · Solo material · `HDU-001 esc. 14`

```gherkin
Escenario: los insumos de mano de obra no entran en la explosión
  Dado un concepto cuyo análisis tiene un insumo MATERIAL y un insumo MANO_OBRA
  Cuando se calcula la explosión
  Entonces solo aparece la fila del insumo MATERIAL
  Y el insumo MANO_OBRA no produce fila ni rechazo, aunque le falte rendimiento
```

### CA-4 `[M]` · Importe de venta e importe sugerido por tipo de partida · `PA-03` · `HDU-001 esc. 15`

```gherkin
Escenario: el sugerido resta los cargos de utilidad e indirectos del análisis
  Dado un concepto del tipo MUROS con cantidad 100
  Y su análisis tiene precio unitario 641.36, cargo INDIRECTOS de 60.00, cargo UTILIDAD de 50.00 y cargo IVA de 40.00
  Cuando se calcula la explosión
  Entonces el importe de venta de MUROS es 100 × 641.36 = 64136.00
  Y el importe sugerido de MUROS es 100 × (641.36 − 50.00 − 60.00) = 53136.00
  Y el IVA no se resta
  Y el precio unitario de la fila del catálogo no interviene, aunque sea distinto o esté ausente
  Y el resultado marca el importe sugerido como sugerencia, sin ningún campo de tope
```

### CA-5 `[M]` · Sin redondeo intermedio · `PA-23`

```gherkin
Escenario: la suma conserva la precisión completa y solo la salida se cuantiza
  Dado conceptos cuyas cantidades por rendimiento producen más decimales que la escala de la columna
  Cuando se calcula la explosión
  Entonces cada cifra se calcula con todos sus decimales antes de agregar
  Y solo la salida se lleva a su escala (cantidad 4, rendimiento 6, importes 4) con ROUND_HALF_UP
  Y el total redondeado una sola vez difiere del que se obtendría redondeando cada producto, en un caso construido para que difiera
```

### CA-6 `[M]` · Rechazo · Datos del concepto incompletos · `HDU-001 esc. 14`

```gherkin
Escenario: un concepto sin tipo, sin análisis o con cantidad no positiva impide toda la explosión
  Dado una obra con un concepto válido
  Y un concepto MURO-X sin tipo de partida en la fila 12
  Y un concepto PLAF-Y sin análisis asociado en la fila 30
  Y un concepto PLAF-Z sin cantidad en la fila 31
  Y un concepto PLAF-W con cantidad 0 en la fila 32
  Cuando se calcula la explosión
  Entonces el resultado es un rechazo y no contiene ninguna fila de explosión ni ningún importe
  Y el rechazo enumera las cuatro causas, cada una con su código de concepto, su fila y su causa

Escenario: un análisis sin precio unitario o sin los cargos que resta el sugerido rechaza el cálculo
  Dado un concepto MURO-A cuyo análisis no tiene precio unitario
  Y un concepto MURO-B cuyo análisis no tiene cargo UTILIDAD
  Y un concepto PLAF-C cuyo análisis tiene cargo INDIRECTOS sin importe
  Cuando se calcula la explosión
  Entonces el resultado es un rechazo con tres causas, cada una con su código de concepto, su fila y el dato o el cargo que falta
  Y ningún cargo ausente se toma como cero
```

### CA-7 `[M]` · Rechazo · Insumo inutilizable o sugerido negativo · invariante 8

```gherkin
Escenario: un insumo material sin rendimiento positivo o sin costo rechaza el cálculo
  Dado un concepto MURO-A cuyo análisis tiene el insumo PANEL sin rendimiento
  Y otro concepto MURO-B cuyo análisis tiene el insumo TORNILLO sin costo unitario
  Y otro concepto MURO-C cuyo análisis tiene el insumo CINTA con rendimiento 0
  Cuando se calcula la explosión
  Entonces el resultado es un rechazo con tres causas, cada una con su código de concepto, su fila y su clave de insumo
  Y ninguna división por cero llega a ocurrir

Escenario: la misma clave de insumo con dos unidades rechaza el cálculo
  Dado dos conceptos cuyos análisis tienen la clave de insumo PANEL, uno en M2 y otro en PZA
  Cuando se calcula la explosión
  Entonces el resultado es un rechazo que nombra la clave PANEL y las dos unidades
  Y no se suma ninguna cantidad de unidades distintas

Escenario: un sugerido negativo rechaza el cálculo
  Dado un tipo de partida cuyos cargos de utilidad e indirectos suman más que su precio unitario
  Cuando se calcula la explosión
  Entonces el resultado es un rechazo que nombra el tipo de partida y su importe sugerido negativo
  Y ninguna cifra negativa sale del cálculo
```

### CA-8 `[M]` · Explosión sintética completa · `HDU-001 esc. 14`

```gherkin
Escenario: el libro sintético reproduce su total calculado a mano
  Dado el libro sintético del diseño, con conceptos de al menos dos tipos de partida, insumos compartidos entre tipos y entre conceptos, y un insumo de mano de obra
  Cuando se lee con los lectores de TKT-013 y TKT-014b, se asigna el tipo de cada concepto y se calcula la explosión
  Entonces el número de filas, la cantidad presupuestada de cada una y el importe total coinciden exactamente con los esperados
  Y el mismo insumo en dos tipos de partida produce dos filas, una por tipo
```

### CA-9 `[M]` · Rechazo · El rendimiento congelado no se altera · `RN-24` · invariante 19

```gherkin
Escenario: el resultado es inmutable y no admite un rendimiento observado
  Dado una explosión calculada
  Cuando se intenta cambiar el rendimiento congelado de una de sus filas
  Entonces la operación falla y la fila conserva su valor
  Y el cálculo no recibe ni produce ningún rendimiento observado
```

### CA-10 `[M]` · Reconciliación con el archivo real

```gherkin
Escenario: la explosión de toda la obra reproduce el archivo de explosión real
  Dado que las variables de entorno apuntan al catálogo, al libro de análisis y al archivo AP-058-25 de la misma obra
  Cuando se calcula la explosión agregada de toda la obra
  Entonces coincide con el archivo AP-058-25 en número de insumos, cantidad de cada uno e importe total

Escenario: sin las variables de entorno la prueba se omite con su motivo
  Dado que alguna de las variables de entorno no está definida
  Cuando corre la suite
  Entonces la prueba queda omitida con un motivo explícito, no en verde
```

### CA-R1 `[M]` · Regresión · Dominio puro y sin `float`

```gherkin
Escenario: la regla nueva respeta las fronteras del dominio
  Dado el código nuevo de presupuesto/dominio/
  Cuando corren verificar_float, ruff check y lint-imports
  Entonces los tres pasan
  Y la regla no importa nada fuera de la biblioteca estándar y tipos_base, ni usa datetime, os ni ningún módulo de E/S
```

### CA-R2 `[M]` · Regresión · Los lectores no cambian

```gherkin
Escenario: las pruebas de TKT-013 y TKT-014b siguen en verde
  Dado la suite existente de los lectores
  Cuando corre después del cambio
  Entonces ninguna prueba de TKT-013 ni de TKT-014b cambia ni falla
```

## Definition of Ready — INVEST

| | Criterio | ¿Pasa? | Nota |
|---|---|---|---|
| **I** | Independiente en valor y despliegue | Sí | Solo depende de TKT-014b, fusionado. No depende de TKT-015 ni de `PA-T8`: el tipo llega como entrada |
| **N** | Describe el qué, no impone el cómo | Sí | Fórmulas y causas de rechazo; ni archivos ni firmas. «`presupuesto/dominio/`» es la capa que exige la regla 2, no una decisión de diseño |
| **V** | Un rol del PRD obtiene algo que hoy no tiene | Sí, con reserva | El valor llega al Director de Proyectos y a Dirección cuando TKT-017 lo persiste y lo sirve; por sí solo habilita TKT-017 |
| **E** | Estimable sin investigar antes | Sí | Talla S. Las fórmulas quedaron fijadas por la persona dueña |
| **S** | Cabe en una sesión sin romper contexto | Sí | Una regla de dominio, un fixture y sus pruebas |
| **T** | Sus criterios se pueden ejecutar | Sí, con reserva | `CA-10` solo se ejecuta con el archivo real fuera del repositorio; en CI queda omitido con motivo |

Ningún fallo; dos reservas (V y T).

## Definition of Done

La del tipo funcionalidad, de [`sdd/metodologia.md`](../../metodologia.md) §8.

- [ ] Cada criterio `[M]` con su prueba, nombrada con su escenario (`test_hdu001_esc14_…`, `test_hdu001_esc15_…`), escrita antes que el código
- [ ] `ruff`, `mypy`, `lint-imports` y `verificar_float` limpios
- [ ] La regla lleva `RN-24` y `PA-01` en su docstring
- [ ] `PA-23` marcada como cerrada en el PRD, con la fecha de la decisión
- [ ] La documentación afectada actualizada en el mismo cambio (arquitectura §7.4, si el diseño añade una operación de `tipos_base`)

## Preguntas abiertas y supuestos

| # | Supuesto o pregunta | Impacto si es falso | Estado |
|---|---|---|---|
| PA-16.1 | El tipo de partida de cada concepto llega asignado desde fuera; quién lo asigna y cómo es `PA-T8` de TKT-013 | Si el mapeo nunca existe, TKT-017 no puede invocar el cálculo con datos reales | Decidido 2026-11-03; `PA-T8` sigue abierta para TKT-017/018 |
| PA-16.2 | Rendimiento y costo de cada fila son promedios ponderados | Si negocio quiere el detalle por concepto, cambia el esquema de `explosion_presupuesto` | Decidido 2026-11-03 |
| PA-16.3 | El importe sugerido resta los importes de los cargos `UTILIDAD` e `INDIRECTOS` del análisis por unidad, multiplicados por la cantidad; el IVA no se resta | Si la fórmula es otra, cambia `M2` y `CA-4` | Decidido 2026-11-03 |
| PA-16.4 | La explosión solo incluye insumos `MATERIAL` | Si la mano de obra debe entrar, depende de `PA-T6` | Decidido 2026-11-03 |
| PA-16.5 | El costo unitario sale del análisis leído, no de `precio_insumo` | Si sale del catálogo de precios, el cálculo necesita precios cargados antes | Decidido 2026-11-03 |
| PA-16.6 | La prueba con el archivo real se omite en CI y la reconciliación de 27 insumos y $2,755,187.21 depende de que el libro de análisis de esa obra se pueda asociar (`PA-T3` de TKT-014) | Si nunca se puede asociar, `CA-10` queda omitido siempre | Decidido 2026-11-03; `PA-T3` sigue abierta |
| PA-16.7 | Hallazgos del borrador OpenAPI: `x-tickets` de `obtener_explosion_insumos` debería ser solo `[TKT-017]`, y `RenglonExplosion.importe_venta` vale cantidad × costo, es decir, un costo | Si no se corrigen, el cliente generado nombra mal el campo | Se corrigen en TKT-017 (decisión 2026-11-03). Resuelta en TKT-017b2 el 2026-11-09: `RenglonExplosion.importe_venta` pasó a `importe_costo` y `x-tickets` de `obtener_explosion_insumos` pasó a `[TKT-017]` |
| PA-16.8 | El importe de venta y el sugerido usan el precio unitario del análisis, no el del catálogo | Si negocio quiere el del catálogo, Union Square rechaza todos sus conceptos por `#REF!` | Decidido 2026-11-03 |
| PA-16.9 | Un análisis sin cargo `UTILIDAD` o `INDIRECTOS`, o con su importe vacío, rechaza el cálculo | Si un tipo de obra legítimamente no lleva utilidad, nunca se podrá calcular su explosión | Decidido 2026-11-03 |
| PA-16.10 | Cantidad o rendimiento menores o iguales que cero rechazan el cálculo | Si un rendimiento cero es legítimo (insumo listado sin consumo), el archivo real rechazaría | Decidido 2026-11-03 |
| PA-16.11 | La misma clave con dos unidades rechaza el cálculo, aunque TKT-015 ya lo bloquee antes | Ninguno: es defensa redundante | Decidido 2026-11-03 |

## Pasada adversarial

Resultado de `abogado-del-diablo` sobre esta spec.

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | El precio unitario del concepto tenía dos orígenes posibles —el catálogo y el análisis— y Union Square trae `#REF!` en el del catálogo; restar cargos del análisis a un precio de otra fuente mezclaba orígenes | La persona dueña decidió el 2026-11-03 usar el precio unitario del análisis. `M2`, `CA-4` y `PA-16.8` |
| 2 | Alta | `M2` no decía qué hacer con un análisis sin cargo `UTILIDAD` o `INDIRECTOS`; tomarlo como cero sugeriría un tope inflado sin aviso | La persona dueña decidió el 2026-11-03 rechazar. `M4`, segundo escenario de `CA-6` y `PA-16.9` |
| 3 | Media | Un rendimiento o una cantidad en cero deja la cantidad presupuestada en cero y el costo ponderado en una división por cero | La persona dueña decidió el 2026-11-03 rechazar todo valor menor o igual que cero. `M4`, `CA-6`, `CA-7` y `PA-16.10` |
| 4 | Media | La misma clave de insumo con dos unidades sumaría metros cuadrados con piezas si llegara al cálculo, aunque TKT-014b ya lo reporte como `UNIDAD_EN_CONFLICTO` | La persona dueña decidió el 2026-11-03 añadirla como causa de rechazo defensiva. `M4`, `CA-7` y `PA-16.11` |

## Contexto técnico

- Módulo `presupuesto`, capa `dominio/`. La interfaz publicada (`cimenta/presupuesto/interfaz.py`) está vacía; exponer la regla a TKT-017 lo decide el diseño.
- Entrada disponible hoy: `leer_libro_presupuesto` (`backend/cimenta/presupuesto/infraestructura/lector_catalogo.py`) devuelve `AnalisisDelLibro` con `catalogo`, `analisis` (cada `AnalisisLeido` con `insumos: InsumoLeido` y `cargos: CargoLeido`) y `asociaciones` de hoja a código. `ConceptoLeido` (`dominio/catalogo.py`) trae `cantidad`, `precio_unitario` y `ruta.partida.nombre`. `TipoInsumo` y `TipoCargo` en `dominio/analisis.py`.
- `tipos_base` (`backend/tipos_base/numericos.py`): `Cantidad(14,4) × Rendimiento(18,6) → Cantidad`, `Cantidad × Dinero → Dinero`, `sumar()`, `cuantizar()` con `ROUND_HALF_UP`. No existe `Dinero × Rendimiento` (`PA-T11` de TKT-004); las divisiones del promedio ponderado tampoco están todas.
- Escalas destino (migración `v0007`): `cantidad_presupuestada numeric(14,4)`, `rendimiento_congelado numeric(18,6)`, `costo_unitario numeric(14,4)`, `importe_venta numeric(18,4)`, `presupuesto_control.importe_sugerido numeric(18,4) NOT NULL`.
- Ruta consumidora (TKT-017): `GET /lineas-base/{linea_base_id}/explosion`, `operationId` `obtener_explosion_insumos`, esquemas `ExplosionInsumos` y `RenglonExplosion` en [`docs/api/openapi.yaml`](../../../docs/api/openapi.yaml). `listar_presupuesto_control` muestra el sugerido.
- Pruebas reales: las variables `CIMENTA_CATALOGO_ENITI` y `CIMENTA_CATALOGO_UNION` ([arranque local](../../../docs/arranque-local.md)) ya existen; la del archivo `AP-058-25` es nueva.
- Fixtures relacionados: `backend/tests/test_tipos_base_explosion.py` (27 renglones sintéticos de TKT-004, que dejó la reconciliación real a este ticket), `soporte_tkt013.py`, `soporte_tkt014.py`.
