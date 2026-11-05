# Spec · TKT-072 · Concepto único por obra y sus apariciones por área

> [← index](_index.md) | Siguiente: `design.md` (lo escribe `/sdd-disenar`)

## Contexto y problema

El esquema de TKT-011 modela el concepto como una fila que lleva a la vez su identidad —código, descripción y unidad— y su lugar en la obra: la partida de un área, la cantidad, el precio unitario y el importe. El invariante 13 lo hace único por obra (`uq_concepto_obra_id_codigo`, `UNIQUE (obra_id, codigo)`). Los dos Excel reales no caben en ese modelo: **cada código se repite en muchas áreas**, una vez por partida. Ninguno de los dos se podría confirmar jamás; es `PA-T1` de TKT-013, que la persona dueña resolvió el 2026-11-05 separando el concepto de sus apariciones.

Medición sobre los dos archivos reales, hecha el 2026-11-05 con `leer_libro_presupuesto` sobre las copias de `D:\Documentos\Miich\Documentos\`:

| | ENITI Torre 5 | Union Square F2 |
|---|---|---|
| Filas de concepto y códigos distintos | 5,028 filas, 36 códigos | 4,281 filas, 31 códigos |
| Partidas y áreas distintas | 726 partidas, 202 áreas | 420 partidas, 148 áreas |
| Códigos repetidos dentro de una misma partida o de una misma área | 0 | 0 |
| Códigos con más de una unidad o más de una descripción | 0 | 0 |
| Códigos con más de un precio unitario | 1: `620040-A`, con `414.93` y `428.19` | No medible: todos los precios son `#REF!` |

Tres hechos condicionan la especificación:

- **El precio unitario no es del concepto.** `620040-A` tiene dos precios en ENITI según el área. Si el precio viviera en el concepto, el archivo real tendría que rechazarse o perder uno de los dos. La persona dueña decidió el 2026-11-05 que el precio unitario viaje con la aparición, como viene en el Excel.
- **El detalle por área tiene consumidores.** La copia congelada (`linea_base_concepto`) solo alcanza el área a través de `concepto.partida_id`. Si apuntara al concepto único, la línea base perdería el área que necesita el alcance de destajo en la fase 2 (`alcance_destajo`, TKT-047) y que el borrador OpenAPI ya devuelve por fila en `ConceptoLineaBase`. La persona dueña decidió el 2026-11-05 que la copia apunte a la aparición.
- **Nada escribe todavía en `concepto`.** No hay modelo ORM ni repositorio; solo las pruebas escriben filas. El cambio llega antes de que existan datos, y por eso la bajada puede negarse cuando los haya en lugar de reconstruirlos.

## Historia de usuario

**Como** Director de Proyectos
**quiero** que el sistema acepte mi catálogo tal como lo trabajo —el mismo concepto repetido en cada área donde se ejecuta, con su cantidad y su precio en cada una—
**para** poder confirmar la línea base de una obra real sin tener que deformar el Excel para que pase.

## Alcance

| Nivel | Ítem |
|---|---|
| **Must** | **M1.** `concepto` queda como el concepto único por obra: código, descripción y unidad. Conserva `uq_concepto_obra_id_codigo` (invariante 13) y la comprobación de la unidad contra el catálogo cerrado (invariante 27). Deja de llevar partida, cantidad, precio unitario e importe |
| **Must** | **M2.** Tabla nueva `partida_concepto` —término del glosario: **concepto de partida**—, la aparición de un concepto en una partida de un área, con cantidad, precio unitario e importe. Cantidad, precio e importe no negativos (invariante 8). Un concepto aparece a lo sumo una vez por partida, y el motor lo impide. Claves foráneas al concepto y a la partida sin borrado en cascada. Sin `obra_id` propio: la obra se alcanza por el concepto |
| **Must** | **M3.** La copia congelada `linea_base_concepto` apunta a la aparición, no al concepto. El disparador de inmutabilidad y la revocación de `UPDATE`, `DELETE` y `TRUNCATE` del invariante 14 siguen intactos |
| **Must** | **M4.** La migración sube y baja contra PostgreSQL real, con el rol de migración. La subida se niega con un mensaje explícito si existe alguna fila en `concepto` o en `linea_base_concepto`, sin tocar nada. La bajada se niega con un mensaje explícito si existe alguna fila en `partida_concepto` o en `concepto` (decisión del 2026-11-05 en el gate de diseño: un concepto sin aparición se perdería en silencio al recrear la tabla); sin filas, deja el esquema exactamente como lo dejó la migración anterior. El rol de aplicación tiene sobre `partida_concepto` los mismos permisos que hoy tiene sobre `concepto`, y el de solo lectura, `SELECT` |
| **Must** | **M5.** Documentación en el mismo cambio: [modelo de datos](../../../docs/03-modelo-datos.md) (diagrama de §4.1 y §4.2, invariantes 8, 13 y 14, y la unicidad de concepto y partida registrada como invariante nuevo de §13, con los conteos de invariantes al día en `CLAUDE.md`, `README.md` y `llms.txt` por autorización de la persona dueña del 2026-11-05, y la decisión «El código de concepto no es global»), [glosario](../../../docs/glosario.md) (*Concepto*, *Catálogo de conceptos* y la entrada nueva *Concepto de partida*), un ADR con las opciones descartadas, y `PA-T1` marcada como resuelta en las specs de TKT-013 y TKT-015 |
| **Must** | **M6.** Regresión: las suites de TKT-010, TKT-011 y TKT-013 a TKT-016 siguen en verde, ajustadas solo donde el modelo nuevo lo exige. La preparación de TKT-015 (`importacion.preparacion`), que ya guarda una entrada por fila del catálogo, no cambia de formato |
| **Should** | — |
| **Could** | — |
| **Won't** | Materializar la jerarquía o congelar (TKT-017) · asignar tipos de partida (TKT-017 y TKT-018, `PA-T8`) · `UNIQUE (apu.concepto_id)` y la coherencia de `concepto.obra_id` en el motor (ticket futuro de `PA-T3` de TKT-011) · `obra_id` en la aparición · qué cuentan el escenario 5 de HDU-001 y `ResumenImportacion.conceptos` (TKT-018) · un catálogo maestro de conceptos entre obras · rutas, casos de uso o pantallas |

## Non-goals

- No escribe conceptos ni apariciones desde ningún caso de uso: solo cambia el esquema. La primera escritura real es la materialización de TKT-017.
- No cambia el lector, la clasificación ni la preparación de la importación.
- No cambia el borrador OpenAPI: `ConceptoLineaBase` ya devuelve una fila por aparición con su nivel y su área.
- No añade la unicidad del APU por concepto ni ninguna otra restricción que `PA-T3` de TKT-011 dejó para su propio ticket.
- No toca la explosión de TKT-016, que trabaja en memoria por fila.

## Reglas de negocio implicadas

Ninguna `RN-xx` gobierna el modelo de conceptos. El ticket protege invariantes del esquema y deja preparado el dato que usan reglas de otros tickets.

| Regla o invariante | Qué exige | Dónde está |
|---|---|---|
| Invariante 13 | Un concepto es único por obra | [Modelo de datos §13](../../../docs/03-modelo-datos.md) |
| Invariante 8 | Cantidades, precios e importes no negativos | Modelo de datos §13 |
| Invariante 14 | La copia congelada no se altera | Modelo de datos §13; [ADR-031](../../../docs/adr/20261101-inmutabilidad-de-la-linea-base-en-el-motor.md) |
| Invariante 27 | La unidad pertenece al catálogo cerrado | Modelo de datos §13 |
| `RN-01` (consumidor) | El presupuesto de venta se congela al firmar | PRD §8. La copia apunta a la aparición para que conserve cantidad, precio e importe por área |
| `PA-01` (consumidor) | La jerarquía se conserva para el catálogo, no para el control | PRD, supuestos |

## Invariantes que deben sobrevivir al cambio

El ticket modifica un esquema que ya existe y que prueban las suites de TKT-010, TKT-011 y TKT-015.

| Invariante | Qué protege | Criterio de regresión |
|---|---|---|
| 13 · `uq_concepto_obra_id_codigo` | Un código por obra; el mismo código en otra obra se admite | `CA-2`, `CA-R1` |
| 27 · `ck_concepto_unidad` | La unidad del concepto pertenece al catálogo | `CA-R1` |
| 8 · no negativos | Cantidad, precio e importe ≥ 0, ahora en la aparición | `CA-4` |
| 14 · copia inmutable | Disparador `IN001` y revocación sobre `linea_base_concepto` | `CA-6` |
| Permisos por rol | La aplicación no gana ni pierde privilegios; la revocación de la copia sigue | `CA-7` |
| Esquema construido con `alembic upgrade head` | Las pruebas nunca crean tablas con `create_all()` | `CA-R2` |
| Preparación de TKT-015 | Formato 1, una entrada por fila | `CA-R3` |

## Criterios de aceptación

Ningún criterio expone una ruta: los rechazos son del motor y se verifican por su `SQLSTATE` y su restricción nombrada. TKT-017 los traducirá al contrato de error cuando materialice. Las cifras de los ejemplos salen de la medición de ENITI.

### CA-1 `[M]` · El mismo concepto en varias áreas · invariante 13 · `HDU-001 esc. 14`

```gherkin
Escenario: un código repetido por área es un concepto con varias apariciones
  Dado una obra con dos áreas, cada una con una partida
  Cuando se escribe el concepto 620001 una vez
  Y se escribe una aparición de 620001 en la partida de cada área, con su cantidad, su precio unitario y su importe
  Entonces existe un solo concepto 620001 en la obra
  Y existen dos apariciones, cada una con la cantidad, el precio y el importe de su área
```

### CA-2 `[M]` · Rechazo · Segundo concepto con el mismo código en la obra · invariante 13

```gherkin
Escenario: el motor rechaza un código repetido en la misma obra
  Dado una obra con el concepto 620001
  Cuando se escribe otro concepto 620001 en la misma obra
  Entonces el motor responde 23505 por la restricción uq_concepto_obra_id_codigo
  Y la obra conserva un solo concepto 620001

Escenario: el mismo código en otra obra se admite
  Dado una obra con el concepto 620001
  Cuando se escribe el concepto 620001 en otra obra
  Entonces las dos obras tienen su concepto 620001
```

### CA-3 `[M]` · Precio por aparición · `HDU-001 esc. 14`

```gherkin
Escenario: el mismo concepto conserva un precio distinto en cada área
  Dado el concepto 620040-A de una obra
  Cuando se escribe una aparición con precio unitario 414.93 y otra con 428.19, en partidas de áreas distintas
  Entonces las dos apariciones se guardan con su precio
  Y el concepto no tiene ninguna columna de precio, cantidad ni importe
```

### CA-4 `[M]` · Rechazo · Aparición inválida · invariante 8

```gherkin
Escenario: el motor rechaza una aparición repetida en la misma partida
  Dado una aparición del concepto 620001 en una partida
  Cuando se escribe otra aparición del concepto 620001 en la misma partida
  Entonces el motor responde 23505 por la restricción de unicidad de concepto y partida
  Y la partida conserva una sola aparición de 620001

Escenario: el motor rechaza una aparición sin concepto o sin partida existentes
  Cuando se escribe una aparición que apunta a un concepto o a una partida inexistentes
  Entonces el motor responde 23503 por la clave foránea correspondiente

Escenario: el motor rechaza cantidades, precios o importes negativos
  Cuando se escribe una aparición con cantidad, precio unitario o importe negativos
  Entonces el motor responde 23514 por la restricción de no negatividad de esa columna
```

### CA-5 `[M]` · Rechazo · Borrar con dependientes

```gherkin
Escenario: no se borra un concepto con apariciones ni una partida con apariciones
  Dado un concepto con una aparición en una partida
  Cuando se borra el concepto, o se borra la partida
  Entonces el motor responde 23001, porque las claves foráneas son ON DELETE RESTRICT, y el concepto, la partida y la aparición siguen existiendo
```

### CA-6 `[M]` · La copia congelada apunta a la aparición · invariante 14 · `HDU-001 esc. 14` · `HDU-001 esc. 18`

```gherkin
Escenario: la copia de una línea base guarda la aparición y alcanza su área
  Dado una línea base en BORRADOR y una aparición de 620001 en una partida del área 312
  Cuando se escribe su copia en linea_base_concepto
  Entonces la copia referencia esa aparición
  Y desde la copia se alcanzan su partida, su área y su nivel

Escenario: la copia congelada sigue siendo inmutable
  Dado una línea base CONGELADA con su copia
  Cuando el rol de aplicación intenta insertar una fila en su copia
  Entonces el disparador la rechaza con IN001 y un mensaje que empieza por RN-01
  Cuando el rol de aplicación intenta modificar, borrar o truncar una fila de su copia
  Entonces el motor la rechaza con 42501, por la revocación de privilegios
  Y la copia conserva sus valores

Escenario: la copia no apunta a una aparición inexistente
  Cuando se escribe una copia que referencia una aparición inexistente
  Entonces el motor responde 23503
```

### CA-7 `[M]` · Rechazo · Permisos por rol

```gherkin
Escenario: la aplicación tiene sobre la aparición lo mismo que tenía sobre el concepto
  Dado el esquema migrado
  Cuando se consultan los privilegios de cimenta_aplicacion y del rol de solo lectura
  Entonces la aplicación tiene SELECT, INSERT, UPDATE y DELETE sobre concepto y sobre partida_concepto
  Y el rol de solo lectura solo tiene SELECT sobre las dos
  Y la aplicación sigue sin UPDATE, DELETE ni TRUNCATE sobre linea_base_concepto

Escenario: el rol de solo lectura no escribe apariciones
  Cuando el rol de solo lectura intenta insertar una aparición
  Entonces el motor responde 42501
```

### CA-8 `[M]` · Migración reversible

```gherkin
Escenario: subir y bajar sin datos deja el esquema como estaba
  Dado una base migrada hasta la revisión anterior a este ticket
  Cuando se sube a head y se baja a la revisión anterior, con el rol de migración
  Entonces el esquema de concepto, linea_base_concepto y sus restricciones es idéntico al de antes de subir
  Y partida_concepto no existe

Escenario: la subida se niega con conceptos o copias escritos
  Dado una base en la revisión anterior con al menos una fila en concepto o en linea_base_concepto
  Cuando se sube a head
  Entonces la subida falla con un mensaje que nombra la tabla con filas y el motivo
  Y el esquema y las filas quedan como estaban

Escenario: la bajada se niega con conceptos o apariciones escritos
  Dado una base en head con al menos una fila en partida_concepto, o un concepto sin ninguna aparición
  Cuando se baja a la revisión anterior
  Entonces la bajada falla con un mensaje que nombra la tabla con filas y el motivo
  Y el esquema y las filas quedan como estaban
```

### CA-9 `[M]` · Documentación coherente

```gherkin
Escenario: el modelo de datos, el glosario y el ADR dicen lo mismo que la migración
  Dado el cambio completo
  Cuando corren python tools/verificar_docs.py, python tools/extraer_mermaid.py y python -m unittest discover -s tools/tests
  Entonces los tres pasan
  Y docs/03 muestra concepto sin cantidad ni precio y partida_concepto con ellos, en el diagrama y en §13
  Y el glosario define Concepto sin cantidad y Concepto de partida con ella
  Y las specs de TKT-013 y TKT-015 marcan PA-T1 como resuelta el 2026-11-05 por TKT-072
```

### CA-R1 `[M]` · Regresión · Restricciones conservadas del concepto

```gherkin
Escenario: el concepto conserva su unicidad y su unidad
  Dado el esquema migrado
  Cuando se inspeccionan las restricciones de concepto
  Entonces uq_concepto_obra_id_codigo sigue siendo UNIQUE (obra_id, codigo)
  Y ck_concepto_unidad sigue admitiendo exactamente las ocho unidades del catálogo
```

### CA-R2 `[M]` · Regresión · Suites existentes

```gherkin
Escenario: las suites que nombran concepto siguen en verde
  Dado el cambio completo
  Cuando corren las suites de TKT-010, TKT-011, TKT-013, TKT-014, TKT-015 y TKT-016 contra PostgreSQL real, con el esquema de alembic upgrade head y el rol de aplicación
  Entonces todas pasan
  Y cada prueba modificada lo está solo porque nombra una columna o una tabla que el modelo nuevo movió
```

### CA-R3 `[M]` · Regresión · Preparación sin cambio de formato

```gherkin
Escenario: la preparación de una importación sigue guardando una entrada por fila
  Dado un libro sintético con el mismo código en dos áreas
  Cuando se analiza con el caso de uso de TKT-015
  Entonces importacion.preparacion conserva el formato 1 y tiene dos entradas de concepto, una por fila
```

## Definition of Ready — INVEST

| | Criterio | ¿Pasa? | Nota |
|---|---|---|---|
| **I** | Independiente en valor y despliegue | Sí | Depende de TKT-011b y TKT-015b, archivados. Solo cambia el esquema |
| **N** | Describe el qué, no impone el cómo | Sí, con reserva | Nombra la tabla `partida_concepto` y su término porque los decidió la persona dueña; columnas exactas, nombres de restricciones y orden de la migración son del diseño |
| **V** | Un rol del PRD obtiene algo que hoy no tiene | Sí, con reserva | El Director de Proyectos podrá confirmar un Excel real cuando exista TKT-017; por sí solo desbloquea TKT-017 |
| **E** | Estimable sin investigar antes | Sí | Talla M; las dependientes de `concepto` están inventariadas |
| **S** | Cabe en una sesión sin romper contexto | Sí | Una migración, sus pruebas y la documentación |
| **T** | Sus criterios se pueden ejecutar | Sí | Todos contra PostgreSQL real con testcontainers |

Ningún fallo; dos reservas (N y V).

## Definition of Done

La del tipo funcionalidad, de [`sdd/metodologia.md`](../../metodologia.md) §8.

- [ ] Cada criterio `[M]` con su prueba, escrita antes que la migración, nombrada con su escenario (`test_hdu001_esc14_…`, `test_hdu001_esc18_…`) o con el ticket donde no hay escenario
- [ ] La migración probada en los dos sentidos con el rol de migración, y las pruebas conectadas con el rol de aplicación
- [ ] `ruff`, `mypy`, `lint-imports` y `verificar_float` limpios
- [ ] Documentación de `M5` en el mismo cambio, con los conteos de invariantes (38 → 39) y de ADR al día en `CLAUDE.md`, `README.md` y `llms.txt`

## Preguntas abiertas y supuestos

| # | Supuesto o pregunta | Impacto si es falso | Estado |
|---|---|---|---|
| PA-T72.1 | El concepto único lleva código, descripción y unidad; la aparición, cantidad, precio unitario e importe | Si negocio quiere un precio por concepto, ENITI se rechaza por `620040-A` | Decidido 2026-11-05 |
| PA-T72.2 | La aparición se llama `partida_concepto` y su término es *concepto de partida* | — | Decidido 2026-11-05 |
| PA-T72.3 | La copia congelada apunta a la aparición | Si apuntara al concepto, la línea base perdería el área que necesita TKT-047 | Decidido 2026-11-05 |
| PA-T72.4 | Un concepto aparece a lo sumo una vez por partida, y el motor lo impide | Si un Excel futuro repite un código dentro de una partida, se rechaza; hoy no ocurre en ninguno de los dos | Decidido 2026-11-05, con la medición |
| PA-T72.5 | La aparición no lleva `obra_id` | Las consultas por obra pasan por `concepto` | Decidido 2026-11-05 |
| PA-T72.6 | La unicidad del APU por concepto sigue fuera | Un concepto podría tener dos APU hasta su ticket | Decidido 2026-11-05 |
| PA-T72.7 | La bajada se niega si hay filas en `partida_concepto` o en `concepto` | Revertir con datos exige un plan manual | Decidido 2026-11-05; ampliado a `concepto` en el gate de diseño (`P-1`) |
| PA-T72.8 | Ningún entorno tiene hoy filas en `concepto` ni en `linea_base_concepto` `(asumido)`: ninguna ruta las escribe y las pruebas de semilla lo afirman, pero no se comprobó en el entorno `test` de la VPS (TKT-070) | Si las hay, la subida se niega (`M4`) y el despliegue se detiene hasta decidir qué hacer con ellas | Decidido 2026-11-05: la subida se niega con datos. Se comprueba antes de desplegar |
| PA-T72.10 | El importe de la aparición no se verifica contra cantidad × precio unitario en el motor, igual que hoy en `concepto` | Un importe incoherente lo detecta la importación (TKT-013), no el motor | Fuera de alcance: no se amplía el ticket |
| PA-T72.9 | El precio unitario de `620040-A` en Union Square no se puede medir (`#REF!`) | Ninguno para este ticket: el precio vive en la aparición | Informativa |

## Pasada adversarial

Resultado de `abogado-del-diablo` sobre esta spec.

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | Qué hace la subida si ya hay filas en `concepto` o en `linea_base_concepto` quedaba en manos del diseño, y es una decisión sobre datos | La persona dueña decidió el 2026-11-05 que la subida se niegue con datos. `M4`, `CA-8` y `PA-T72.8` |
| 2 | Media | `CA-6` aceptaba «IN001 o falta de privilegio», y un mutante que quitara el disparador seguiría en verde | `CA-6` exige `IN001` para la inserción y `42501` para modificar, borrar o truncar |
| 3 | Media | La unicidad de concepto y partida es un invariante nuevo y mueve el conteo de 38 que citan `CLAUDE.md`, `README.md` y `llms.txt` | La persona dueña autorizó el 2026-11-05 registrarla como invariante nuevo y actualizar los tres conteos. `M5` |
| 4 | Baja | El motor no comprueba que el importe de la aparición sea cantidad por precio | Igual que hoy en `concepto`; queda fuera para no ampliar el ticket. `PA-T72.10` |

## Contexto técnico

- Esquema actual: `backend/migraciones/versions/v0006_presupuesto_estructura_y_catalogos.py` (`concepto` con `uq_concepto_obra_id_codigo`, `ck_concepto_unidad`, los tres `ck_concepto_*_no_negativo`, `fk_concepto_partida_id`; `apu.concepto_id` sin `UNIQUE`; permisos a `cimenta_aplicacion`) y `v0007_presupuesto_linea_base_e_importacion.py` (`linea_base_concepto` con `fk_linea_base_concepto_concepto_id`, disparador `trg_linea_base_concepto_inmutable` sobre `presupuesto_proteger_copia_congelada()`, `REVOKE` y guarda de bajada con `LOCK`, que sirven de patrón). `v0009` añade `importacion.preparacion`.
- `partida.tipo_partida_id` es `NOT NULL` (`v0006`): la asignación de tipo de `PA-T8` ocurre antes de materializar, en TKT-017.
- Nada de producción escribe en `concepto`: `infraestructura/tablas.py` solo declara `importacion`, `importacion_error` e `insumo`.
- Pruebas que nombran `concepto`: `backend/tests/conftest.py` (fábrica `concepto()`, `copia_concepto`, armado de línea base e inventario de restricciones), `test_tkt011_estructura.py`, `test_tkt011_permisos.py` (lista literal de tablas), `test_tkt011_linea_base.py`, `test_tkt011_migracion_linea_base.py`, `test_tkt015_esquema.py` (afirma `UNIQUE (obra_id, codigo)`), `test_tkt010_migracion.py` y `test_tkt010_semilla_local.py` (listas de tablas vacías).
- Dominio en memoria sin cambios: `ConceptoLeido` (`dominio/catalogo.py`), `Preparacion` (`dominio/preparacion_importacion.py`, formato 1 de [ADR-036](../../../docs/adr/20261105-preparacion-de-importacion-en-jsonb.md)), `ConceptoAExplotar` (`dominio/explosion.py`).
- Borrador OpenAPI: `ConceptoLineaBase` ya devuelve una fila por aparición con `nivel`, `area` y `tipo_partida`; no cambia.
- La medición de esta spec se hizo con un script de un solo uso en el directorio temporal de la sesión, sobre `leer_libro_presupuesto`; el diseño la repite en su fila de arranque si la necesita.
