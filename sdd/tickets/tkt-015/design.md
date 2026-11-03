# Design · TKT-015 · Validaciones y reporte de errores por fila

> [← index](_index.md) | [← spec](spec.md) | Siguiente: `impl.md` (lo escribe `/sdd-ejecutar`)

## Estrategia

La clasificación vive **entera en `dominio/`**, como funciones puras sobre el `AnalisisDelLibro` que ya devuelve `leer_libro_presupuesto`: una tabla exhaustiva `TIPO_POR_CAUSA` lleva cada una de las 22 `CausaHallazgo` a uno de los siete tipos de `importacion_error`, una tabla de mensajes en español la acompaña, y dos detecciones propias de este ticket (`SIN_APU` desde `codigos_sin_analisis` y `DUPLICADO` literal desde el catálogo) completan la lista. El dominio decide también qué conceptos y qué análisis quedan fuera de la preparación, el estado final de la importación y si una importación admite el análisis. Los lectores de TKT-013 y TKT-014 no cambian su resultado.

La **preparación se guarda como una columna `jsonb` nueva en `importacion`**, escrita en el mismo `UPDATE` que fija el estado final y en la misma transacción que inserta los errores en lote: o queda completa, o no queda. Una restricción `CHECK` nueva impide que exista mientras la importación está `RECIBIDO` o `ANALIZANDO`, así que el reintento la borra por construcción.

El **trabajo** corre en un `ProcessPoolExecutor` de un trabajador que gobierna un único hilo despachador del proceso del API. El despachador mantiene su propia cola, envía al trabajador **un análisis a la vez**, refresca el `latido` de todas las importaciones que tiene a su cargo —la que corre y las que esperan turno— y escribe el progreso que el hijo le manda por una cola de `multiprocessing`. El hijo no toca la base. El **barrido de arranque** es un paquete nuevo fuera de `cimenta/`, `trabajos/`, que recibe definiciones (tabla, estado intermedio, estado vencido, columna de marca, umbral y gancho) y no conoce ningún módulo; `presupuesto` publica la suya en su interfaz y `servidor/` las ejecuta en el `lifespan` antes de servir, **solo si la base está configurada**: sin variables de base la aplicación sigue arrancando, como garantiza TKT-006 (P16).

El orden suma unas **3,170 líneas**, casi ocho veces el tope de unas 400 por cambio: es la **condición de parada 3**. Se propone partir en **TKT-015a** (escenarios 28 y 29, clasificación, preparación, migración y caso de uso síncrono, con los archivos reales) y **TKT-015b** (ejecutor en proceso aparte, latido, progreso, barrido reutilizable y arranque), con un PR cada uno y fusión a → b.

## Partición propuesta (condición de parada 3)

| Ticket | Musts | Contenido | Migración | Líneas estimadas | Depende de | Filas |
|---|---|---|---|---|---|---|
| TKT-015a | `M1` a `M4` y `S1`; regresión `CA-R1` a `CA-R3` | Escenarios 28 y 29 de HDU-001; `dominio/importacion.py`, `dominio/clasificacion_importacion.py`, `dominio/preparacion_importacion.py`; `infraestructura/tablas.py`, `repositorio_importacion.py`, `preparacion_json.py`, `trabajo_analisis.py`; `aplicacion/analisis_importacion.py` (síncrono); `herramientas/soporte_tkt015.py`; pruebas sintéticas y reales; ADR-036 | `v0009` · columna `preparacion` y su `CHECK` | ~1,790 (≈ 780 de producción, ≈ 800 de pruebas, ≈ 210 de documentación) | TKT-014b (archivado) | A-pre, A0, A1, A2a, A2b, A3 a A9 |
| TKT-015b | `M5`, `M6`, `M7`; `CA-R1` del lector con avance; `CA-R2` del paquete nuevo | `trabajos/barrido.py`; contrato de lista blanca en `backend/pyproject.toml`; `aplicacion/barrido_importacion.py`; `al_avanzar` en el lector; `infraestructura/ejecutor_analisis.py`; `SeguimientoImportacion` y `solicitar_analisis`; ajustes; `variables_de_base_presentes`; `lifespan` con sus dos casos; interfaz con `__all__`; `--cov=trabajos`; ajustes a cinco suites existentes; ADR-037 | Ninguna | ~1,380 (≈ 520 de producción, ≈ 700 de pruebas nuevas y editadas, ≈ 160 de documentación) | TKT-015a | B0, B1, B1b, B2 a B7 |

**El orden de fusión es fijo: a → b.** TKT-015 queda como paraguas, conserva la spec y este diseño, y se cierra cuando se cierran los dos. **TKT-017** (confirmación) y **TKT-059** (que reutiliza `trabajos/`) dependen de TKT-015b; **TKT-018** depende de TKT-017. **TKT-016 no depende de TKT-015**: `docs/05` lo hace depender solo de TKT-014b, y la explosión no necesita el análisis persistido.

**Por qué esta frontera.** TKT-015a es todo lo que decide qué está roto y qué se conserva, y se prueba de punta a punta de forma síncrona: la prueba llama a `iniciar_analisis`, a `analizar_contenido` y a `registrar_resultado` en el mismo hilo, contra PostgreSQL real. No hay procesos, hilos ni arranque. TKT-015b es todo lo que decide **dónde y cuándo** corre eso, y no cambia ninguna clasificación: solo envuelve `analizar_contenido` en el trabajador y añade el barrido.

**Alternativas descartadas.** Partir en tres (dominio puro · persistencia y archivos reales · trabajo y barrido): cada entrega bajaría a unas 900 a 1,400 líneas, más cerca del precedente de TKT-014 (~830 y ~935), a costa de una ceremonia de PR más (objeción 12 de la pasada adversarial; se deja como opción en P1). Recortar `S1` ahorra unas 15 líneas, no un PR.

### Criterios de la spec que hay que ajustar si se aprueba la partición

| Criterio | Dice hoy | Debe decir |
|---|---|---|
| `CA-1` a `CA-11`, `CA-S1` | «se analiza la importación» | TKT-015a: se ejecutan en secuencia `iniciar_analisis`, `analizar_contenido` y `registrar_resultado`, en el hilo de la prueba |
| `CA-11` esc. 2 | «un análisis que falla antes de terminar» | TKT-015a: `registrar_interrupcion` tras `iniciar_analisis` (TC-32). TKT-015b lo repite con una excepción y con la muerte real del trabajador (TC-58, TC-59) |
| `CA-12` a `CA-17` | — | Se completan en TKT-015b. TKT-015a cubre solo la parte síncrona de `CA-12` (TC-23), `CA-14` (TC-03), `CA-15` (TC-03 y TC-34) y `CA-16` (TC-37); `CA-13` y `CA-17` son solo de TKT-015b |
| `CA-18` esc. 2 | «el análisis arranca de nuevo» | TKT-015a: `iniciar_analisis` devuelve el `TrabajoAnalisis` (TC-34). TKT-015b: `solicitar_analisis` lo encola y el análisis corre (TC-61) |
| `CA-R1` | Los lectores no cambian | TKT-015a: las suites de TKT-013 y TKT-014 intactas. TKT-015b: además, el parámetro `al_avanzar` no cambia el resultado (TC-50) |

## Escalera de decisión

| Objeto | Peldaño donde paró | Por qué |
|---|---|---|
| Ampliar `ck_importacion_error_tipo` o `apu_cargo.tipo` | 1 · Won't | Decisión de la persona dueña del 2026-11-02; las 18 causas sin tipo propio van al más cercano |
| Una causa nueva `RENDIMIENTO_AUSENTE` en el lector | 1 · descartado | Cambiaría lo que devuelve el lector (TC-14 de TKT-014 espera `VALOR_AUSENTE` en `F`) y rompería `CA-R1`. El lector ya marca la celda; la clasificación lee su papel en el `AnalisisLeido` (ver «Rendimiento ausente») |
| `TipoErrorImportacion`, `EstadoImportacion`, `MotivoInterrupcion`, `ErrorImportacion`, `TrabajoAnalisis` (a) | 5 · objeto nuevo | No existe ningún objeto de valor del error persistible ni del estado de la importación. Una prueba sincroniza los dos enumerados con sus `CHECK` (TC-18) |
| `TIPO_POR_CAUSA` y la tabla de mensajes (a) | 5 · objeto nuevo | `M1` y `CA-10`. Un `Mapping` inmutable recorrible por la prueba; una función por causa no se podría comprobar exhaustiva |
| `Hallazgo` como entrada de la clasificación | 3 · reuso | Trae causa, hoja, fila, columna, valor original y detalle: todo lo que pide `M1` salvo el mensaje, que arma la clasificación |
| `normalizar_clave_insumo` para la descripción de `DUPLICADO` | 3 · reuso | Es la normalización de ADR-035 (recorte, espacios interiores colapsados, mayúsculas) que `PA-15.13` asume |
| `normalizar_codigo` para agrupar códigos | 3 · reuso | La misma que usa `asociar_analisis`; así `SIN_APU` y `DUPLICADO` agrupan igual que la asociación |
| `detectar_duplicados`, `errores_sin_apu`, `clasificar_libro`, `armar_preparacion` (a) | 5 · objeto nuevo | Ningún lector produce `DUPLICADO` ni `SIN_APU`, y nada decide qué se conserva. Funciones puras pequeñas |
| `puede_analizarse`, `estado_tras_analisis` (a) | 5 · objeto nuevo | Son la máquina de estados de arquitectura §9 restringida a este ticket. En `dominio/` para que `aplicacion/` no lleve el `if` de negocio |
| Preparación en tablas normalizadas (`importacion_concepto`…) | 1 · descartado | Cinco o seis tablas nuevas, unas 5,000 inserciones por análisis y su espejo en ORM, para un dato que se lee entero una vez |
| Preparación como `bytea` con `pickle` | 1 · descartado | Deserializar `pickle` desde la base es ejecución de código, ata el dato a la forma de las clases de Python y el rol de lectura no lo puede leer |
| Tabla propia `importacion_preparacion` 1:1 | 1 · descartado | Misma atomicidad que la columna, con una tabla, una clave foránea y un `DELETE` más en el reintento |
| Columna `importacion.preparacion jsonb` y `ck_importacion_preparacion_tras_analisis` (a) | 4 · cambio mínimo | Una columna anulable en la fila que ya guarda `resumen jsonb`; el `CHECK` es nativo y sostiene «completa o ninguna» en el reintento. No toca ningún invariante: ni el 13 ni el `CHECK` de tipos |
| `infraestructura/tablas.py` con `Table` de Core (a) | 5 · objeto nuevo | `presupuesto` no tiene todavía modelos. Solo las columnas que se usan, con `naming_convention`; nunca emiten DDL |
| `repositorio_importacion.py` (a y b) | 5 · objeto nuevo | No existe repositorio de `presupuesto`. Funciones de una sentencia cada una; ninguna confirma |
| `preparacion_json.py` (a) | 5 · objeto nuevo | Serializa `Decimal` como cadena con `format(valor, "f")`, sin cuantizar. `Dinero.serializar()` no sirve: rechaza lo no cuantizado |
| `analizar_contenido` y `ResultadoAnalisis` (a) | 5 · objeto nuevo | La función que corre en el hijo: lee, clasifica y serializa. Devuelve tipos simples |
| Transición `RECIBIDO → ANALIZANDO` con `SELECT … FOR UPDATE` (a) | 2 · nativo | El bloqueo de fila serializa dos solicitudes; la segunda ve `ANALIZANDO` y recibe el conflicto. El rol de aplicación ya tiene `UPDATE` sobre `importacion` |
| Inserción de errores con `execute(insert(...), [dict, …])` (a) | 2 · nativo | *Executemany* de SQLAlchemy 2.x en la transacción del caso de uso (Context7, «Execute Insert with a list of parameter dictionaries»). Sin `COPY` |
| `ConflictoEstado(codigo="ESTADO_NO_PERMITE_OPERACION")` y `NoEncontrado` | 3 · reuso | Ya están en `contrato_error` y en el catálogo cerrado (`PA-15.7`) |
| Índice `(estado, latido)` en `importacion` | 1 · YAGNI | Cientos de filas, no millones; el barrido corre una vez por arranque. Se revisa si la tabla pasa de unas 10,000 filas |
| Bitácora del análisis y del barrido | 1 · Won't | `PA-15.8` |
| Paquete `trabajos/` con `DefinicionBarrido`, `barrer` y `barrer_todas` (b) | 5 · objeto nuevo | `M7`. Fuera de `cimenta/` porque el contrato `esqueleto-modulos` es exhaustivo (exige exactamente diez módulos) y porque `archivos` no puede importar `presupuesto`. Sigue el patrón de `tipos_base/` —paquete raíz de `import-linter` con su propio contrato de lista blanca—, **no** el de `contrato_error/`, que ADR-022 dejó fuera de `root_packages` y cuya pureza vigila una prueba |
| `UPDATE … WHERE estado = :intermedio AND (marca IS NULL OR marca < now() - :umbral) RETURNING id` (b) | 2 · nativo | En `READ COMMITTED`, el segundo `UPDATE` concurrente espera el bloqueo de fila y vuelve a evaluar el `WHERE` sobre la versión confirmada: la fila ya no está en el estado intermedio y no se toca. El reloj es el de la base |
| `trabajos` en `root_packages` y contrato `trabajos-solo-sqlalchemy` de tipo `lista_blanca` en `backend/pyproject.toml` (b) | 4 · cambio mínimo | `import-linter` solo lee `backend/pyproject.toml` (no hay `.importlinter`). Sin el paquete raíz, `lint-imports` no lo analiza y `CA-17` no se puede verificar. Obliga a tocar tres suites de fronteras y cuatro aserciones de la cuenta de contratos (ver «Contratos en `pyproject.toml`») |
| `definicion_barrido_importacion` y su gancho (b) | 5 · objeto nuevo | Lo único específico de la importación: insertar el `PROCESO_INTERRUMPIDO` en la misma transacción |
| Parámetro `al_avanzar` de `leer_libro_presupuesto` (b) | 4 · cambio mínimo | Opcional, solo por nombre, con `None` por omisión. El resultado no cambia (TC-50). Sin él, el progreso no se mueve mientras el hijo lee, y `M5` pide progreso «mientras corre». No toca ningún invariante |
| Progreso por hitos fijos sin canal entre procesos | 1 · descartado | El progreso quedaría en cero durante toda la lectura |
| El hijo escribe latido y progreso con su propia conexión | 1 · descartado | Un latido escrito por el hijo no dice si el proceso del API vive, y la importación que espera turno no tendría quien la refresque (`PA-15.4`) |
| `EjecutorAnalisis` con un hilo despachador y cola propia (b) | 5 · objeto nuevo | Enviar al grupo un trabajo a la vez hace que un `BrokenProcessPool` afecte solo a la importación que corría: el grupo roto marca fallidos todos los futuros pendientes (`_terminate_broken`; Context7, `Lib/concurrent/futures/process.py`) |
| `multiprocessing.Queue` entregada por `initializer` e `initargs` (b) | 2 · nativo | La forma documentada de compartir una cola con un proceso del grupo. Pasarla por `submit` falla con `RuntimeError` (E-5, ejecutado en Windows) |
| Contexto `spawn` explícito (b) | 2 · nativo | El mismo en Windows y Linux; `fork` con hilos vivos es inseguro y el método por omisión cambió en 3.14 (Context7) |
| Tiempo máximo por análisis con `terminate_workers()` | 1 · fuera, P12 | Exige Python 3.14 como mínimo (`requires-python` dice 3.13) o API privada; ningún Must lo pide |
| `trabajos_intervalo_latido` y `trabajos_umbral_vencimiento` en `AjustesServidor` (b) | 4 · cambio mínimo | `pydantic-settings` ya lee `CIMENTA_*`; dos campos con valor por omisión y una validación |
| `variables_de_base_presentes(entorno)` en `herramientas/conexion.py` (b) | 4 · cambio mínimo | Una función junto a `leer_variable`. Permite que el `lifespan` respete el invariante de TKT-006 (arrancar sin variables de base) sin intentar una conexión que fallaría (P16) |
| `__all__` en `cimenta/presupuesto/interfaz.py` (b) | 3 · reuso del patrón | Como `cimenta/auditoria/interfaz.py`: `servidor.*` tiene `implicit_reexport = false` en mypy |
| `--cov=trabajos` en `.github/workflows/ci.yml` (b) | 4 · cambio mínimo | Sin él, un paquete nuevo queda fuera de la cobertura en silencio |
| `lifespan` en `crear_aplicacion` (b) | 2 · nativo | Mecanismo de FastAPI para el arranque y el cierre; `on_event` está obsoleto y no convive con `lifespan` (Context7, «Lifespan Events») |

Ningún objeto paró en el peldaño 4 tocando un invariante registrado: la escalera no se rompe. La regla 11 de `CLAUDE.md` se roza en un punto, el `lifespan`, que FastAPI exige `async`; se resuelve sin romperla (ver «Arranque») y se pregunta en P13. La revisión de impacto encontró un choque real con un invariante declarado de TKT-006 (CA-R4 y D-2: la aplicación arranca sin variables de base); el `lifespan` se rediseñó para respetarlo y la vía elegida se pregunta en P16.

## Mapa de causas a tipos (`PA-15.2`, para aprobación)

Reglas generales, en `clasificar_hallazgo`:

1. El tipo sale de `TIPO_POR_CAUSA[hallazgo.causa]`, salvo la excepción del rendimiento.
2. `hoja`, `fila`, `columna` y `valor_original` se copian del hallazgo, salvo en las cinco causas de hoja (marcadas «hoja» abajo), que se persisten con `fila` y `columna` nulas (`CA-9`); la fila del encabezado, si la hay, va en el mensaje. Una ubicación que el lector ya trae nula (por ejemplo, `VALOR_AUSENTE` por un rótulo de cabecera ausente, `ANALISIS_SIN_CODIGO` sin rótulo o `CONCEPTO_SIN_PARTIDA`, que no trae columna) se copia nula.
3. El mensaje es la plantilla de la causa, en español, seguida del sufijo «(causa: <CAUSA>)», precedido de un espacio. El sufijo es fijo y las pruebas filtran por él.
4. **La ubicación no se repite en el mensaje**, salvo en las cinco causas de hoja (1 a 5), cuyas columnas de ubicación van nulas, y en las plantillas 18 y 20, donde la hoja forma parte de la frase. Las demás plantillas no llevan `{hoja}` ni `{fila}`.
5. **`SIN_CONCEPTOS` queda solo para las cinco causas de hoja, que además llevan fila y columna nulas**, como dice el borrador OpenAPI. No son las únicas con ubicación nula (ver regla 2), pero sí las únicas `SIN_CONCEPTOS`. Una referencia a una partida, a un nivel de la jerarquía o a un concepto que no existe es una referencia rota: `CONCEPTO_SIN_PARTIDA`, `PROFUNDIDAD_EXCEDIDA` y `CODIGO_SIN_CONCEPTO` van a `REF_ROTA` y conservan la ubicación del hallazgo (corrección del orquestador; la persona dueña la confirma en P2).

| # | Causa cruda | Tipo | Plantilla del mensaje (sin el sufijo) |
|---|---|---|---|
| 1 | `HOJA_NO_LOCALIZADA` (hoja) | `SIN_CONCEPTOS` | `El libro no tiene una hoja de catálogo reconocible ({detalle}).` más un espacio y la estructura mínima |
| 2 | `HOJA_AMBIGUA` (hoja) | `SIN_CONCEPTOS` | `El libro tiene más de una hoja que parece de catálogo ({detalle}); debe haber una sola.` más un espacio y la estructura mínima |
| 3 | `ENCABEZADO_NO_LOCALIZADO` (hoja) | `SIN_CONCEPTOS` | `La hoja «{hoja}» no trae ninguna fila de concepto: ninguna fila tiene «Código» en la columna A.` más un espacio y la estructura mínima |
| 4 | `COLUMNA_NO_LOCALIZADA` (hoja) | `SIN_CONCEPTOS` | `La hoja «{hoja}» no trae ninguna fila de concepto legible: en el encabezado de la fila {fila}, la columna «{valor}» {detalle}.` más un espacio y la estructura mínima |
| 5 | `NINGUN_CONCEPTO` (hoja) | `SIN_CONCEPTOS` | `La hoja «{hoja}» no trae ninguna fila de concepto: debajo del encabezado de la fila {fila} no hay ninguna fila con código.` más un espacio y la estructura mínima |
| 6 | `ERROR_DE_FORMULA` | `REF_ROTA` | `La celda trae el error de fórmula «{valor}»: su valor no se puede leer y no se importa como cero.` |
| 7 | `NO_ES_NUMERO` | `REF_ROTA` | `La celda trae «{valor}» donde se esperaba un número.` |
| 8 | `VALOR_AUSENTE` | `REF_ROTA`; `RENDIMIENTO_AUSENTE` en la celda de rendimiento | `La celda está vacía y se esperaba un valor{ ({detalle})}.` · en rendimiento: `El insumo no trae rendimiento: sin él no se puede calcular cuánto consume el concepto.` |
| 9 | `UNIDAD_NO_RECONOCIDA` | `UNIDAD_DESCONOCIDA` | `La unidad «{valor}» no está entre las ocho admitidas: M2, ML, PZA, KG, CAJA, SACO, ROLLO y JORNAL.` |
| 10 | `NOMBRE_ILEGIBLE` | `REF_ROTA` | `El nombre del nivel, área o partida trae el error de fórmula «{valor}».` |
| 11 | `CONCEPTO_SIN_PARTIDA` | `REF_ROTA` | `El concepto no cuelga de ninguna partida: su referencia a la partida que lo agrupa no existe, porque falta la fila de título.` |
| 12 | `PROFUNDIDAD_EXCEDIDA` | `REF_ROTA` | `La fila de título «{valor}» excede los cuatro niveles de la jerarquía (raíz, nivel, área y partida): su referencia a un nivel de la jerarquía no existe.` |
| 13 | `VALOR_NEGATIVO` | `REF_ROTA` | `La celda trae el valor negativo {valor}; el análisis de precio unitario no admite cifras negativas.` |
| 14 | `FECHA_NO_RECONOCIDA` | `REF_ROTA` | `La fecha «{valor}» no tiene la forma de una fecha.` |
| 15 | `CARGO_DESCONOCIDO` | `UNIDAD_DESCONOCIDA` | `El cargo «{valor}» no está en el catálogo de cargos: herramienta menor, andamiaje, desperdicio, viáticos, IVA, indirectos y utilidad.` |
| 16 | `PU_NO_CUADRA` | `REF_ROTA` | `El precio unitario del análisis no coincide con la suma de sus insumos y cargos: {detalle}.` |
| 17 | `PU_NO_VERIFICABLE` | `REF_ROTA` | `El precio unitario del análisis no se puede verificar: {detalle}.` |
| 18 | `ANALISIS_SIN_CODIGO` | `REF_ROTA` | `La hoja «{hoja}» es un análisis de precio unitario sin código: no se puede asociar a ningún concepto.` |
| 19 | `CODIGO_EN_VARIAS_HOJAS` | `DUPLICADO` | `El código «{valor}» tiene análisis también en la hoja {detalle}: un concepto solo puede tener un análisis de precio unitario.` |
| 20 | `CODIGO_SIN_CONCEPTO` | `REF_ROTA` | `El análisis de la hoja «{hoja}» tiene el código «{valor}», que no está en el catálogo: su referencia a un concepto no existe.` |
| 21 | `UNIDAD_EN_CONFLICTO` | `UNIDAD_DESCONOCIDA` | `El insumo aparece con unidades distintas ({detalle}): un insumo tiene una sola unidad.` |
| 22 | `TIPO_EN_CONFLICTO` | `DUPLICADO` | `El mismo insumo aparece como material y como mano de obra ({detalle}): un insumo tiene un solo tipo.` |

La **estructura mínima** es la constante `ESTRUCTURA_MINIMA_DEL_CATALOGO`: `Se espera una sola hoja cuyo nombre empiece por «Catálogo», con una fila de encabezado que lleve «Código» en la columna A y la descripción en la B, las columnas «Unidad», «Cantidad», «P.U.» e «Importe», y debajo al menos una fila con código.` Sale de lo que exigen `elegir_hoja`, `_localizar_encabezado` y `_localizar_columnas` (ADR-033).

**Marcadores.** `{x}` se sustituye por el campo del hallazgo; un `{detalle}`, `{valor}` o `{fila}` nulo se escribe `sin dato`. Un tramo opcional `{ ({detalle})}` solo aparece si `detalle` no es nulo: `La celda está vacía y se esperaba un valor (sin rótulo «fecha» en la cabecera).` frente a `La celda está vacía y se esperaba un valor.`. En la causa 1, si `detalle` es nulo, se omite el paréntesis.

Los tres tipos que produce este ticket sin causa cruda, sin sufijo:

| Origen | Tipo | Ubicación y valor | Mensaje |
|---|---|---|---|
| Cada código de `codigos_sin_analisis` | `SIN_APU` | Hoja del catálogo, fila de la **primera** aparición del código (`PA-15.14`), columna `A`, `valor_original` el código | `El concepto con código «{codigo}» no tiene hoja de análisis de precio unitario. Sin ese análisis no se puede calcular la explosión de insumos de ese concepto.` |
| Cada código del catálogo con dos o más descripciones normalizadas distintas | `DUPLICADO` | Hoja del catálogo, primera fila del código, columna `A`, `valor_original` el código | `El código «{codigo}» aparece con descripciones distintas en las filas {todas las filas}: {grupos}. Un código identifica un solo concepto.` |
| Interrupción (`MotivoInterrupcion`) | `PROCESO_INTERRUMPIDO` | Las tres nulas | Ver «Interrupciones» |

El código va en la columna `A` porque `_localizar_columnas` exige `«Código»` en el índice 0.

**Listas en español** (`_enumerar(elementos: Sequence[str]) -> str`): un elemento, tal cual; dos, unidos por «y» entre espacios; tres o más, separados por coma y espacio, y el último con «y» entre espacios. Sirve para las filas y para los grupos.

**Grupos del mensaje de `DUPLICADO`.** Un grupo por descripción normalizada, en orden de primera aparición, con la primera forma original recortada: `«{texto}» en la fila {N}` si el grupo tiene una fila, y `«{texto}» en las filas {_enumerar(filas)}` si tiene varias. Los grupos se unen con `_enumerar`. Ejemplos:

- Dos grupos (`CA-7`): `El código «620001» aparece con descripciones distintas en las filas 12, 45 y 90: «MURO STD» en las filas 12 y 45 y «PLAFON» en la fila 90. Un código identifica un solo concepto.`
- Tres grupos: `El código «620002» aparece con descripciones distintas en las filas 20, 30, 40 y 50: «MURO» en las filas 20 y 50, «PLAFON» en la fila 30 y «CAJILLO» en la fila 40. Un código identifica un solo concepto.`

**Recuento de los archivos reales con este mapa** (E-1, ejecutado el 2026-11-03 por el revisor, coincide con la spec):

| | `REF_ROTA` | `UNIDAD_DESCONOCIDA` | `SIN_APU` | `DUPLICADO` | `SIN_CONCEPTOS` | Total |
|---|---|---|---|---|---|---|
| ENITI Torre 5 | 6 (5 `ERROR_DE_FORMULA` y 1 `ANALISIS_SIN_CODIGO`) | 20 (`CARGO_DESCONOCIDO`) | 16 | 6 (`CODIGO_EN_VARIAS_HOJAS`) | 0 | **48** (`CA-10`) |
| Union Square F2 | 8,608 (8,562 `ERROR_DE_FORMULA`, 21 `NOMBRE_ILEGIBLE`, 20 `ANALISIS_SIN_CODIGO` y 5 `CONCEPTO_SIN_PARTIDA`) | 0 | **31** (`CA-3`) | 0 | 0 | 8,639 |

`ANALISIS_SIN_CODIGO` no va a `SIN_APU` a propósito: si fuera, Union tendría 51 errores `SIN_APU` y `CA-3` («31 errores `SIN_APU`») fallaría sin defecto. E-1 confirmó además que no hay dos hallazgos sobre la misma celda entre fuentes, y que `ANALISIS_SIN_CODIGO` y `CODIGO_EN_VARIAS_HOJAS` traen la hoja del APU, fila 12 y columna `C`.

### Rendimiento ausente sin causa nueva

El lector solo trae causa y columna, pero el `AnalisisLeido` trae además la estructura de la hoja. `es_celda_de_rendimiento(hallazgo, analisis)` devuelve `True` si y solo si:

- el hallazgo está en `analisis.hallazgos` (no en el catálogo ni en los del libro),
- su causa es `VALOR_AUSENTE`,
- su columna es `_COLUMNA_RENDIMIENTO = "F"` (la columna de rendimiento de ADR-035 y E-1 de TKT-014),
- y su fila es la de un `InsumoLeido` de ese análisis cuyo `rendimiento is None`.

Así, la unidad vacía del insumo (`D`), el analista vacío (`B`), un cargo sin base (`E`) o una celda vacía del catálogo en la columna `F` no son `RENDIMIENTO_AUSENTE` (`CA-6`). `NO_ES_NUMERO`, `VALOR_NEGATIVO` y `ERROR_DE_FORMULA` en la celda de rendimiento siguen siendo `REF_ROTA`: el tipo dice «ausente», y esas celdas traen algo. No es un hallazgo nuevo inferido (`CA-R1`): es el mismo `VALOR_AUSENTE` que el lector ya marcó, clasificado por la celda en que cayó. TC-08 fija la letra contra `analizar_hoja_apu` real.

### Conceptos y análisis que quedan fuera de la preparación

`clasificar_libro` devuelve, además de los errores, `filas_rechazadas` y `hojas_rechazadas`:

- Una fila de concepto está **rechazada** si algún error con `hoja == catalogo.hoja` cae en su fila, **o** si su código normalizado tiene un `SIN_APU` de `errores_sin_apu` o un `DUPLICADO` de `detectar_duplicados`. Esos dos, y solo esos, son errores de código del catálogo, y rechazan **todas** las filas del código, no solo la primera (P3).
- Los `DUPLICADO` que vienen de `CODIGO_EN_VARIAS_HOJAS` y de `TIPO_EN_CONFLICTO` llevan **la hoja del APU** y rechazan **solo su análisis, nunca filas del catálogo**. Si rechazaran filas, ENITI perdería en la preparación los conceptos de `620014`, `620045` y `620050`, que sí son válidos en el catálogo. TC-14 lo prueba.
- Un análisis está **rechazado** si algún error cae en su hoja (de lectura, de asociación o de insumos). Sus asociaciones tampoco entran.
- Los errores de un análisis **no** rechazan los conceptos del catálogo: el error es del análisis, y el concepto ya queda sin análisis válido en la preparación.

`filas_leidas = len(catalogo.conceptos)`, `filas_rechazadas` es el tamaño del conjunto de filas rechazadas **intersectado con `{c.fila for c in catalogo.conceptos}`**, porque un error en una fila de título o de área (por ejemplo `NOMBRE_ILEGIBLE`) no rechaza ningún concepto y una cuenta literal contaría filas de más; TC-14 incluye ese caso. `filas_validas` es la diferencia (`PA-15.9`). En ENITI quedan rechazados **23 de los 24 análisis** (los veinte con `SIROC`, los cinco con `#REF!` en la cabecera, los seis con código en dos hojas y el que no tiene código, con solapes): su preparación lleva un solo análisis. En Union, los 4,281 conceptos traen `#REF!` y quedan todos rechazados.

### Orden de los errores

Determinista en memoria, para que las pruebas (TC-13) sean estables. **No promete orden al almacenar**: `importacion_error` no tiene columna de orden y su `id` es aleatorio, de modo que el orden de inserción no se puede recuperar. TKT-018 debe ordenar la consulta con `ORDER BY hoja, fila, columna, id`, con los nulos al final, como pide el borrador OpenAPI («por hoja y fila»). El orden en memoria es: los hallazgos del catálogo en el orden del lector, los `DUPLICADO` del catálogo en orden de primera aparición del código, los `SIN_APU` en el orden de `codigos_sin_analisis`, los hallazgos de cada análisis en el orden de las hojas y, al final, los hallazgos del libro.

## Preparación persistida (`PA-15.12`)

### Alternativas

| | Columna `jsonb` en `importacion` | Tabla `importacion_preparacion` 1:1 | Tablas normalizadas | `bytea` con `pickle` |
|---|---|---|---|---|
| Completa o ninguna | El mismo `UPDATE` que fija el estado; el `CHECK` la impide en `RECIBIDO` y `ANALIZANDO` | Misma transacción; hace falta borrarla en el reintento | Misma transacción, unas 5,000 inserciones | Igual que la columna |
| Migración | Una columna y un `CHECK` | Tabla, clave foránea, índice | Cinco o seis tablas | Una columna |
| Permisos | Heredan los de la tabla (0001) | Los por omisión, más `DELETE` en uso | Los por omisión | Heredan |
| Lectura por TKT-017 y TKT-018 | Un `SELECT` de una columna | Un `SELECT` con unión | Consultas por parte | `pickle.loads` sobre datos de la base |

**Elegida: columna `jsonb`.** Es la única que da «completa o ninguna» sin una sentencia extra, y el `CHECK` hace imposible que una preparación vieja sobreviva al reintento. E-8 (ejecutado el 2026-11-03 por el revisor) confirmó que el `CHECK` se evalúa sobre la fila nueva: pasar a `ANALIZANDO` con la preparación puesta da `23514`, y el `UPDATE` que la limpia pasa.

**Tamaño esperado** `(sin ejecutar, E-3)`: unos 250 bytes por concepto en JSON, así que ENITI con 5,028 conceptos ronda 1.3 MB de texto si todos fueran válidos; en la práctica menos, porque ENITI rechaza las filas de sus 16 códigos sin APU. PostgreSQL lo comprime y lo saca de la página (TOAST); el límite de un `jsonb` es 1 GB. **Si `pg_column_size` pasa de 20 MB, A6 se detiene y se escala.**

**Los repositorios nunca leen `preparacion` salvo `leer_preparacion`**: cada consulta de `importacion` nombra sus columnas.

### Formato 1

`preparacion_a_json(preparacion: Preparacion) -> dict[str, object]`, en `infraestructura/preparacion_json.py`. Reglas:

- **Cifras:** `str | null`. Un valor de `tipos_base` se escribe `format(x.valor, "f")`, **sin cuantizar** (`Dinero("641.3608310977561")` → `"641.3608310977561"`). **`None` → `null`**, en cifras y en textos. Ninguna cifra pasa por `float`; `json` nunca ve un `Decimal`.
- **Enumerados:** `.value`; un tipo nulo, `null`.
- **Ruta:** la fila de cada nodo, no su nombre.
- `formato: 1` permite que TKT-017 rechace otra versión.

| Clave del JSON | Tipo | De dónde sale |
|---|---|---|
| `formato` | `int` | La constante `FORMATO_PREPARACION = 1` |
| `hoja_catalogo` | `str \| null` | `Preparacion.hoja_catalogo` ← `CatalogoLeido.hoja` |
| `nodos[].fila`, `.profundidad`, `.nombre` | `int`, `str`, `str \| null` | `NodoLeido.fila`, `NodoLeido.profundidad.value`, `NodoLeido.nombre` |
| `conceptos[].fila`, `.codigo` | `int`, `str` | `ConceptoLeido.fila`, `ConceptoLeido.codigo` |
| `conceptos[].descripcion`, `.unidad` | `str \| null` | `ConceptoLeido.descripcion`, `ConceptoLeido.unidad` |
| `conceptos[].cantidad`, `.precio_unitario`, `.importe` | `str \| null` | `ConceptoLeido.cantidad`, `.precio_unitario`, `.importe` (`Cantidad \| None`, `Dinero \| None`) |
| `conceptos[].ruta.raiz`, `.nivel`, `.area`, `.partida` | `int \| null` | `ConceptoLeido.ruta.raiz.fila`… o `null` si el nodo es `None` |
| `analisis[].hoja` | `str` | `AnalisisLeido.hoja` |
| `analisis[].fila_codigo` | `int \| null` | `AnalisisLeido.cabecera.fila_codigo` |
| `analisis[].codigo`, `.unidad`, `.fecha`, `.analista` | `str \| null` | `AnalisisLeido.cabecera.codigo`, `.unidad`, `.fecha`, `.analista` |
| `analisis[].precio_unitario_cabecera` | `str \| null` | `AnalisisLeido.cabecera.precio_unitario` |
| `analisis[].precio_unitario` | `str \| null` | `AnalisisLeido.precio_unitario` (el del pie) |
| `analisis[].fila_precio_unitario` | `int` | `AnalisisLeido.fila_precio_unitario` |
| `analisis[].insumos[].fila`, `.tipo`, `.descripcion`, `.clave` | `int`, `str`, `str`, `str` | `InsumoLeido.fila`, `.tipo.value`, `.descripcion`, `.clave` |
| `analisis[].insumos[].unidad` | `str \| null` | `InsumoLeido.unidad` |
| `analisis[].insumos[].costo_unitario`, `.rendimiento`, `.cargo` | `str \| null` | `InsumoLeido.costo_unitario`, `.rendimiento`, `.cargo` |
| `analisis[].cargos[].fila`, `.rotulo` | `int`, `str` | `CargoLeido.fila`, `.rotulo` |
| `analisis[].cargos[].tipo` | `str \| null` | `CargoLeido.tipo.value` o `null` |
| `analisis[].cargos[].porcentaje`, `.base`, `.importe` | `str \| null` | `CargoLeido.porcentaje`, `.base`, `.importe` |
| `analisis[].totales.material`, `.mano_obra`, `.costo_directo`, `.cargos`, `.precio_unitario` | `str \| null` | `AnalisisLeido.totales.*` (`TotalesAnalisis`, todos `Dinero \| None`) |
| `asociaciones[].hoja`, `.codigo`, `.filas_catalogo` | `str`, `str`, `list[int]` | `AsociacionLeida` |
| `insumos_por_crear[].clave`, `.descripcion`, `.unidad`, `.tipo`, `.creado_en_importacion` | `str`, `str`, `str`, `str`, `bool` | `InsumoPorCrear` |

En la práctica, los conceptos y análisis de la preparación no tienen cifras nulas (un nulo viene siempre de un hallazgo, que los rechaza), pero el formato admite `null` porque el tipo lo admite y la serialización no decide reglas.

## Capas afectadas

### Dominio

| Archivo | Qué | Regla | Ticket |
|---|---|---|---|
| `backend/cimenta/presupuesto/dominio/importacion.py` | Enumerados, `ErrorImportacion`, `TrabajoAnalisis`, `puede_analizarse`, `estado_tras_analisis`, `error_de_interrupcion`, `mapa_de_insumos_existentes`; `progreso_de_lectura` en b | HDU-001 esc. 4, 6 y 29; `RNF-17`; `PA-15.5` a `PA-15.7` | a y b |
| `backend/cimenta/presupuesto/dominio/clasificacion_importacion.py` | `TIPO_POR_CAUSA`, plantillas, `_enumerar`, `clasificar_hallazgo`, `es_celda_de_rendimiento` (A2a); `errores_sin_apu`, `detectar_duplicados`, `clasificar_libro` (A2b) | HDU-001 esc. 6, 7, 8, 9, 27 y 28; `PA-15.1`, `PA-15.2`, `PA-15.13`, `PA-15.14` | a |
| `backend/cimenta/presupuesto/dominio/preparacion_importacion.py` | `Preparacion`, `armar_preparacion` | HDU-001 esc. 6; `PA-15.9` | a |

Todos con `from __future__ import annotations`, solo biblioteca estándar (`dataclasses`, `enum`, `decimal`, `uuid`, `types`, `collections.abc`) y `tipos_base`. Ninguno lleva una `RN-xx`: el docstring cita el escenario de HDU-001, `RNF-17` o la `PA` que implementa.

#### `importacion.py`

```python
class TipoErrorImportacion(StrEnum):   # los siete valores de ck_importacion_error_tipo, en ese orden
class EstadoImportacion(StrEnum):      # los seis de ck_importacion_estado
class MotivoInterrupcion(StrEnum):     # REINICIO, EXCEPCION, TRABAJADOR_TERMINADO, ARCHIVO_ILEGIBLE

@dataclass(frozen=True, slots=True)
class ErrorImportacion:
    tipo: TipoErrorImportacion
    hoja: str | None
    fila: int | None
    columna: str | None
    mensaje: str
    valor_original: str | None

@dataclass(frozen=True, slots=True)
class TrabajoAnalisis:
    importacion_id: UUID
    archivo_id: UUID
    insumos_existentes: Mapping[str, str]   # clave normalizada → unidad; se pasa como dict
```

| Firma | Qué hace |
|---|---|
| `puede_analizarse(estado: EstadoImportacion, tipos_de_error: frozenset[TipoErrorImportacion]) -> bool` | `True` si `estado is RECIBIDO`, o si `estado is CON_ERRORES` y `tipos_de_error == {PROCESO_INTERRUMPIDO}`. En cualquier otro caso, `False` (`CA-18`, `PA-15.7`) |
| `estado_tras_analisis(errores: Sequence[ErrorImportacion]) -> EstadoImportacion` | `VALIDADO` si `len(errores) == 0`; si no, `CON_ERRORES` (`M2`) |
| `error_de_interrupcion(motivo: MotivoInterrupcion) -> ErrorImportacion` | `PROCESO_INTERRUMPIDO` con hoja, fila, columna y valor nulos y el mensaje de «Interrupciones» |
| `mapa_de_insumos_existentes(insumos: Iterable[tuple[str, str]]) -> dict[str, str]` | De pares `(descripcion, unidad)` ya ordenados por `codigo`: `normalizar_clave_insumo(descripcion) → unidad`; si dos claves coinciden, gana la primera (P6) |
| `progreso_de_lectura(hojas_leidas: int, hojas_totales: int) -> Porcentaje` (b) | `Porcentaje(0)` si `hojas_totales <= 0`. Si no, `(Decimal(9 * min(hojas_leidas, hojas_totales)) / Decimal(10 * hojas_totales)).quantize(Decimal("0.000001"), rounding=ROUND_DOWN)` y después `Porcentaje(...)` sobre ese `Decimal`. Queda en `[0, 0.9]`; el `1` lo pone solo el cierre |

**El progreso no usa `Porcentaje.cuantizar()`**, que redondea con `ROUND_HALF_UP` (`tipos_base/numericos.py`): un trabajo que no terminó no debe redondear hacia arriba. `(4, 7)` da `0.514285` con `ROUND_DOWN` y `0.514286` con `ROUND_HALF_UP`; TC-51 los distingue. Como la regla 1 de `CLAUDE.md` dice que los tipos solo redondean con `cuantizar()`, esta excepción se declara `(asumido)` en ADR-037: el progreso no es dinero ni una columna de cálculo, y el redondeo va escrito con escala y modo, como admite `conv-dominio-python` §1 fuera de los tipos.

#### Interrupciones

| Motivo | Quién lo pone | Mensaje |
|---|---|---|
| `REINICIO` | El barrido, y `solicitar_analisis` si el ejecutor está cerrado | `El análisis se interrumpió porque el servidor se reinició o dejó de responder mientras analizaba. El archivo no tiene la culpa: puedes reintentar el análisis.` |
| `EXCEPCION` | El despachador, ante una excepción del trabajo | `El análisis terminó por un error inesperado del analizador. Puedes reintentar el análisis; si se repite, el archivo puede traer algo que el analizador no sabe leer: avisa con el identificador de esta importación.` |
| `TRABAJADOR_TERMINADO` | El despachador, ante `BrokenProcessPool` | `El proceso que analizaba el archivo terminó de forma abrupta. Puedes reintentar el análisis; se hará con un proceso nuevo.` |
| `ARCHIVO_ILEGIBLE` | El despachador, si `leer_contenido` falla | `No se pudo obtener el archivo de la importación para analizarlo. Puedes reintentar el análisis; si se repite, vuelve a subir el archivo como una importación nueva.` |

El nombre de la clase de la excepción y la traza van **solo** al registro estructurado, con `importacion_id` (`CA-14`), nunca al mensaje. El caso de uso lo registra con `registro.error("analisis_interrumpido", exc_info=True, importacion_id=…, motivo=…)` y nunca con `str(exc)`, que `RNF-13` prohíbe: el procesador `resumir_excepcion_del_evento` de `servidor/registro.py` reduce la excepción a su tipo y sus marcos. `cimenta/` no importa `servidor/`; usa `structlog` directamente.

#### `clasificacion_importacion.py`

| Firma | Qué hace | Fila |
|---|---|---|
| `TIPO_POR_CAUSA: Mapping[CausaHallazgo, TipoErrorImportacion]` | `MappingProxyType` con las 22 filas del mapa | A2a |
| `ESTRUCTURA_MINIMA_DEL_CATALOGO: str` | La constante de arriba | A2a |
| `_enumerar(elementos: Sequence[str]) -> str` | Listas en español | A2a |
| `clasificar_hallazgo(hallazgo: Hallazgo, *, es_rendimiento: bool = False) -> ErrorImportacion` | Reglas generales 1 a 5. Lanza `KeyError` si la causa no está en el mapa: es un error de programa, y TC-05 lo impide antes | A2a |
| `es_celda_de_rendimiento(hallazgo: Hallazgo, analisis: AnalisisLeido) -> bool` | Ver «Rendimiento ausente» | A2a |
| `errores_sin_apu(catalogo: CatalogoLeido, codigos_sin_analisis: Sequence[str]) -> tuple[ErrorImportacion, ...]` | Un `SIN_APU` por código, con la fila de la primera aparición (`normalizar_codigo(concepto.codigo) == codigo`) | A2b |
| `detectar_duplicados(catalogo: CatalogoLeido) -> tuple[ErrorImportacion, ...]` | Agrupa los conceptos por `normalizar_codigo(concepto.codigo)`. `ConceptoLeido.codigo` es `str` (`dominio/catalogo.py:75`) y el lector solo crea un concepto cuando la celda del código no está vacía, así que `normalizar_codigo` (que recibe un `ValorCelda` y devuelve `str \| None`, `lectura_analisis.py:68`) devuelve siempre una cadena aquí; el `None` se descarta por tipos, sin rama de negocio. Omite los códigos cuyo texto está en la constante `ERRORES_DE_FORMULA` (`dominio/catalogo.py:20`; ya tienen su `REF_ROTA`) y los conceptos con `descripcion is None` (ya tienen el suyo). Un `DUPLICADO` por código cuyo conjunto de `normalizar_clave_insumo(descripcion)` tiene más de un elemento | A2b |
| `clasificar_libro(libro: AnalisisDelLibro) -> Clasificacion` | Errores en el orden declarado, `filas_rechazadas: frozenset[int]` y `hojas_rechazadas: frozenset[str]` con la regla de «Conceptos y análisis que quedan fuera» | A2b |

`Clasificacion` es `@dataclass(frozen=True, slots=True)` con esos tres campos.

#### `preparacion_importacion.py`

```python
@dataclass(frozen=True, slots=True)
class Preparacion:
    hoja_catalogo: str | None
    nodos: tuple[NodoLeido, ...]
    conceptos: tuple[ConceptoLeido, ...]       # solo los no rechazados, en orden de fila
    analisis: tuple[AnalisisLeido, ...]        # solo los no rechazados, en orden de hoja
    asociaciones: tuple[AsociacionLeida, ...]  # solo las de análisis no rechazados
    insumos_por_crear: tuple[InsumoPorCrear, ...]  # los del lector, tal cual
    filas_leidas: int
    filas_validas: int
    filas_rechazadas: int
```

`armar_preparacion(libro: AnalisisDelLibro, clasificacion: Clasificacion) -> Preparacion`. Los nodos van todos.

### Aplicación

| Archivo | Caso de uso | Transacción y bloqueo | Ticket |
|---|---|---|---|
| `backend/cimenta/presupuesto/aplicacion/analisis_importacion.py` | `iniciar_analisis`, `registrar_resultado`, `registrar_interrupcion`, `obtener_preparacion` | Una transacción por caso de uso con `fabrica_sesiones.begin()`; `FOR UPDATE` en `iniciar_analisis` | a |
| el mismo | `solicitar_analisis`, `SeguimientoImportacion` | `solicitar_analisis` = `iniciar_analisis` y después encolar; cada método de `SeguimientoImportacion`, su transacción corta | b |
| `backend/cimenta/presupuesto/aplicacion/barrido_importacion.py` | `definicion_barrido_importacion(umbral: timedelta) -> DefinicionBarrido` y su gancho `_al_vencer(sesion_bd, ids)` | El gancho escribe en la sesión del barrido, sin confirmar | b |

| Firma | Qué hace, en orden |
|---|---|
| `iniciar_analisis(fabrica_sesiones: sessionmaker[Session], importacion_id: UUID) -> TrabajoAnalisis` | En `with fabrica_sesiones.begin() as sesion_bd:` 1. `repositorio.bloquear_importacion` (`FOR UPDATE`); si es `None`, `NoEncontrado(recurso="importacion", mensaje="La importación no existe.")`. 2. `repositorio.tipos_de_error`. 3. Si `not puede_analizarse(...)`, `ConflictoEstado(codigo="ESTADO_NO_PERMITE_OPERACION", mensaje=f"La importación está en {estado} y no admite el análisis. Solo se analiza una importación RECIBIDO o una CON_ERRORES interrumpida.", detalle={"importacion_id": str(id), "estado": estado})`, sin acciones; la transacción se deshace. 4. `repositorio.borrar_errores` (`PA-15.7`). 5. `repositorio.pasar_a_analizando`. 6. `mapa_de_insumos_existentes(repositorio.insumos_existentes(sesion_bd))`. Devuelve `TrabajoAnalisis` |
| `registrar_resultado(fabrica_sesiones, importacion_id: UUID, resultado: ResultadoAnalisis) -> bool` | Una transacción: `estado = estado_tras_analisis(resultado.errores)`; `repositorio.cerrar_analisis(...)`; si devuelve `False` (ya no estaba `ANALIZANDO`), registra `resultado_descartado` con `structlog` y devuelve `False` sin escribir nada. Si no, `repositorio.insertar_errores(...)` y devuelve `True`. Si la inserción falla, todo se deshace (TC-38) |
| `registrar_interrupcion(fabrica_sesiones, importacion_id: UUID, motivo: MotivoInterrupcion) -> bool` | Una transacción: `repositorio.interrumpir`; si `True`, inserta `error_de_interrupcion(motivo)`. La preparación sigue nula (`CA-11` esc. 2) |
| `obtener_preparacion(fabrica_sesiones, importacion_id: UUID) -> dict[str, object] \| None` | Lectura: `repositorio.leer_preparacion`. No abre el archivo (`CA-11`) |
| `solicitar_analisis(fabrica_sesiones, ejecutor: EjecutorAnalisis, importacion_id: UUID) -> None` (b) | `trabajo = iniciar_analisis(...)`; `ejecutor.encolar(trabajo)`. Si `encolar` lanza `EjecutorCerrado`, `registrar_interrupcion(..., REINICIO)` y relanza (TC-62). Vuelve sin esperar al análisis (`CA-12`) |

`SeguimientoImportacion(fabrica_sesiones)` (b) implementa el protocolo `Seguimiento`:

| Método | Qué hace |
|---|---|
| `latir(ids: Sequence[UUID]) -> None` | `repositorio.refrescar_latido` en su transacción; nada si `ids` está vacía |
| `avanzar(importacion_id: UUID, hojas_leidas: int, hojas_totales: int) -> None` | `repositorio.registrar_progreso(sesion_bd, importacion_id, progreso_de_lectura(...))` |
| `terminar(importacion_id: UUID, resultado: ResultadoAnalisis) -> None` | `registrar_resultado` |
| `interrumpir(importacion_id: UUID, motivo: MotivoInterrupcion) -> None` | `registrar_interrupcion` |

El caso de uso **no asienta en la bitácora** (`PA-15.8`).

### Infraestructura y esquema

| Objeto | Tipo | Detalle | Ticket |
|---|---|---|---|
| `importacion.preparacion` | columna | `jsonb`, anulable, sin valor por omisión | a |
| `ck_importacion_preparacion_tras_analisis` | restricción | `CHECK (preparacion IS NULL OR estado NOT IN ('RECIBIDO', 'ANALIZANDO'))` | a |
| `backend/migraciones/versions/v0009_presupuesto_preparacion_de_importacion.py` | migración | Las dos sentencias, cada una en su `op.execute` | a |
| `backend/cimenta/presupuesto/infraestructura/tablas.py` | `Table` de Core | `importacion` (`id`, `obra_id`, `archivo_id`, `estado`, `progreso`, `filas_leidas`, `filas_validas`, `filas_rechazadas`, `latido`, `preparacion` como `JSONB`), `importacion_error` (las ocho columnas) e `insumo` (`codigo`, `descripcion`, `unidad`), en un `MetaData` con `naming_convention` | a |
| `backend/cimenta/presupuesto/infraestructura/repositorio_importacion.py` | repositorio | Ver tabla de abajo. Ninguna función confirma | a y b |
| `backend/cimenta/presupuesto/infraestructura/preparacion_json.py` | serializador | `FORMATO_PREPARACION = 1`; `preparacion_a_json` | a |
| `backend/cimenta/presupuesto/infraestructura/trabajo_analisis.py` | función del trabajador | `ResultadoAnalisis` y `analizar_contenido` | a |
| `backend/herramientas/soporte_tkt015.py` | apoyo de pruebas | `libro_sintetico`, ayudantes en memoria (a); `trabajo_de_prueba`, `liberar` (b) | a y b |
| `backend/cimenta/presupuesto/infraestructura/lector_catalogo.py` | adaptador | Parámetro `al_avanzar` en `leer_libro_presupuesto` | b |
| `backend/cimenta/presupuesto/infraestructura/ejecutor_analisis.py` | ejecutor | `Seguimiento`, `EjecutorAnalisis`, `EjecutorCerrado`, `resumir_avances`, `ejecutar_en_trabajador`, `notificar_avance` | b |
| `backend/trabajos/__init__.py`, `backend/trabajos/barrido.py` | paquete nuevo | `DefinicionBarrido`, `barrer`, `barrer_todas` | b |
| `backend/pyproject.toml` | configuración | `root_packages` con `trabajos`; contrato `trabajos-solo-sqlalchemy`; `trabajos.*` en el bloque estricto de mypy | b |
| `backend/herramientas/conexion.py` | utilidad | `variables_de_base_presentes(entorno: Mapping[str, str]) -> bool` | b |
| `backend/servidor/ajustes.py`, `backend/servidor/fabrica.py` | arranque | Dos ajustes y el `lifespan` | b |
| `backend/cimenta/presupuesto/interfaz.py` | interfaz | `__all__` con `definicion_barrido_importacion`, `crear_ejecutor_analisis`, `leer_contenido_no_configurado` y `EjecutorAnalisis` | b |
| `.github/workflows/ci.yml` y `tools/tests/test_definicion_ci.py` | pipeline | `--cov=trabajos` y su aserción nueva | b |
| `tests/test_tkt011_linea_base.py` y `tests/test_tkt011_migracion_linea_base.py` | pruebas existentes | El cambio de A4: fijan las columnas y los `CHECK` exactos de `importacion` (`:121-136` y `:322-336`; el conjunto de `CHECK`, `:146-151` y TC-50 en `:575-610`) y la migración los pone rojos | a |
| `tests/test_fronteras_dominio.py`, `tests/test_tkt005_fronteras.py`, `tests/test_tkt007_fronteras.py`, `tests/test_tkt013_regresion.py`, `tests/test_tkt014_lector.py`, `tests/test_tkt057_arranque.py` | pruebas existentes | Los cambios de B1, B3 y B5 | b |

**Migración:** `0009` — reversible: sí · destructiva: sí, solo en la bajada (borra las preparaciones guardadas) · plan de reversa: antes de bajar, `COPY (SELECT id, preparacion FROM importacion WHERE preparacion IS NOT NULL) TO …` o `pg_dump --table=importacion`; la bajada ejecuta `ALTER TABLE importacion DROP CONSTRAINT ck_importacion_preparacion_tras_analisis` y `ALTER TABLE importacion DROP COLUMN preparacion`. Una `CON_ERRORES` interrumpida puede reanalizarse; una `VALIDADO` no: por eso el respaldo. Sin `GRANT` ni `REVOKE`: la columna hereda los privilegios de la tabla. La subida no toca filas: toda fila existente tiene `preparacion` nula y cumple el `CHECK`.

#### Repositorio

| Firma | Sentencia |
|---|---|
| `bloquear_importacion(sesion_bd, importacion_id) -> FilaImportacion \| None` | `SELECT id, obra_id, archivo_id, estado FROM importacion WHERE id = :id FOR UPDATE` |
| `tipos_de_error(sesion_bd, importacion_id) -> frozenset[TipoErrorImportacion]` | `SELECT DISTINCT tipo FROM importacion_error WHERE importacion_id = :id` |
| `borrar_errores(sesion_bd, importacion_id) -> int` | `DELETE FROM importacion_error WHERE importacion_id = :id` |
| `pasar_a_analizando(sesion_bd, importacion_id) -> None` | `UPDATE importacion SET estado = 'ANALIZANDO', progreso = 0, latido = now(), preparacion = NULL, filas_leidas = NULL, filas_validas = NULL, filas_rechazadas = NULL WHERE id = :id` |
| `insumos_existentes(sesion_bd) -> list[tuple[str, str]]` | `SELECT descripcion, unidad FROM insumo ORDER BY codigo` (activos e inactivos: P6) |
| `cerrar_analisis(sesion_bd, importacion_id, *, estado, filas_leidas, filas_validas, filas_rechazadas, preparacion: dict[str, object]) -> bool` | `UPDATE importacion SET estado = :estado, progreso = 1, latido = now(), filas_* = …, preparacion = :preparacion WHERE id = :id AND estado = 'ANALIZANDO' RETURNING id` |
| `interrumpir(sesion_bd, importacion_id) -> bool` | `UPDATE importacion SET estado = 'CON_ERRORES', latido = now() WHERE id = :id AND estado = 'ANALIZANDO' RETURNING id`. El progreso se conserva |
| `insertar_errores(sesion_bd, importacion_id, errores: Sequence[ErrorImportacion]) -> None` | Nada si la lista está vacía; si no, `sesion_bd.execute(insert(importacion_error), [dict, …])` con `uuid.uuid4()` por fila, **las ocho claves en cada diccionario** (también las nulas: el primero fija las columnas) y `tipo=str(error.tipo)`. `str()` y no `.value`: así una cadena suelta inyectada por TC-38 llega a la base y la rechaza el `CHECK`, en vez de caer antes con `AttributeError` |
| `leer_preparacion(sesion_bd, importacion_id) -> dict[str, object] \| None` | `SELECT preparacion FROM importacion WHERE id = :id` |
| `refrescar_latido(sesion_bd, ids: Sequence[UUID]) -> None` (b) | `update(importacion).where(importacion.c.id.in_(ids), importacion.c.estado == "ANALIZANDO").values(latido=func.now())`: `in_` con la lista, nunca un `IN (:ids)` con un parámetro de texto |
| `registrar_progreso(sesion_bd, importacion_id, progreso: Porcentaje) -> None` (b) | `UPDATE importacion SET progreso = GREATEST(COALESCE(progreso, 0), :progreso), latido = now() WHERE id = :id AND estado = 'ANALIZANDO'`. `GREATEST` garantiza que el progreso nunca baja (E-8 lo ejecutó) |

`FilaImportacion` es un `NamedTuple` con `id`, `obra_id`, `archivo_id` y `estado: EstadoImportacion`. El `progreso` se escribe con `progreso.valor`; nunca un `float`.

**Tiempos del rol de aplicación** (`v0001:38-39`): `lock_timeout = 5s` y `statement_timeout = 15s`, por sentencia y para toda conexión del rol (`RNF-16`).

| Sentencia | Riesgo | Cómo se prueba y se mitiga |
|---|---|---|
| `cerrar_analisis`, con una preparación de hasta unos 1.3 MB | Pasar de 15 s y caer con `57014` | E-4 mide la **sentencia sola** con ENITI y con Union |
| `insertar_errores`, unas 8,600 filas | Que una sentencia pase de 15 s | Con psycopg 3 y sin `RETURNING`, SQLAlchemy 2.1.5 envía el lote por `cursor.executemany` (el `use_insertmanyvalues_wo_returning` solo existe en el dialecto de psycopg2), así que cada fila es una sentencia corta y el riesgo es bajo. E-4 sigue midiendo la sentencia más larga y la transacción entera |
| El `FOR UPDATE` de `iniciar_analisis` cuando otra solicitud tiene la fila | La segunda recibiría `55P03` (`lock_not_available`) si la primera tardara más de 5 s | La transacción de `iniciar_analisis` solo hace lecturas cortas, un `DELETE` y un `UPDATE`. TC-35 solo acepta `ConflictoEstado` del perdedor: un `55P03` es fallo de la prueba y se investiga |

**Condición de parada:** si E-4 mide una sentencia de más de 5 s (un tercio del límite), A6 se detiene y se escala. No se sube el `statement_timeout` ni se usa `SET LOCAL` por decisión propia: el límite lo fija `RNF-16`. La traducción de `55P03` o `57014` a `409 CONCURRENCIA` es del manejador global cuando haya ruta (TKT-018); A6 lee `servidor/manejadores.py` y anota en `impl.md` si ya la hace, sin cambiarla.

#### `trabajo_analisis.py` (a)

```python
@dataclass(frozen=True, slots=True)
class ResultadoAnalisis:
    errores: tuple[ErrorImportacion, ...]
    preparacion: dict[str, object]     # formato 1, ya serializado
    filas_leidas: int
    filas_validas: int
    filas_rechazadas: int
```

`analizar_contenido(contenido: bytes, insumos_existentes: Mapping[str, str]) -> ResultadoAnalisis`: `libro = leer_libro_presupuesto(contenido, insumos_existentes)`; `clasificacion = clasificar_libro(libro)`; `preparacion = armar_preparacion(libro, clasificacion)`; devuelve el resultado con `preparacion_a_json(preparacion)`. En b gana `al_avanzar: Callable[[int, int], None] | None = None`, que pasa tal cual al lector.

E-2 (ejecutado el 2026-11-03 por el revisor) confirmó que `AnalisisDelLibro` (813 KB con ENITI, 707 KB con Union), `ErrorImportacion` y `ResultadoAnalisis` sobreviven a `pickle`; aun así el hijo devuelve el resultado ya serializado, para no depender de la forma de `AnalisisDelLibro`.

#### Ejecutor (b)

```python
class Seguimiento(Protocol):
    def latir(self, ids: Sequence[UUID]) -> None: ...
    def avanzar(self, importacion_id: UUID, hojas_leidas: int, hojas_totales: int) -> None: ...
    def terminar(self, importacion_id: UUID, resultado: ResultadoAnalisis) -> None: ...
    def interrumpir(self, importacion_id: UUID, motivo: MotivoInterrupcion) -> None: ...

type FuncionTrabajo = Callable[[UUID, bytes, Mapping[str, str]], ResultadoAnalisis]

class EjecutorCerrado(RuntimeError): ...

class EjecutorAnalisis:
    def __init__(self, *, seguimiento: Seguimiento, leer_contenido: Callable[[UUID], bytes],
                 intervalo_latido: timedelta, trabajo: FuncionTrabajo = ejecutar_en_trabajador) -> None
    def encolar(self, trabajo: TrabajoAnalisis) -> None          # EjecutorCerrado si ya se cerró
    def cerrar(self, *, espera_maxima: float = 10.0) -> None
    def esperar_latidos(self, minimo: int, espera_maxima: float) -> bool
    def esperar_inactivo(self, espera_maxima: float) -> bool

def resumir_avances(mensajes: Sequence[tuple[UUID, int, int]]) -> dict[UUID, tuple[int, int]]
```

- **Construcción perezosa.** No crea procesos ni hilos: el grupo y el hilo despachador nacen en la primera llamada a `encolar`.
- **Grupo de procesos.** `ProcessPoolExecutor(max_workers=1, mp_context=multiprocessing.get_context("spawn"), initializer=_iniciar_trabajador, initargs=(cola_avance,))`, con `cola_avance = contexto.Queue()`. E-5 y E-6 (ejecutados en Windows con Python 3.14.3) confirmaron la cola por `initargs`, el `BrokenProcessPool` ante `os._exit(1)` y un grupo nuevo con otro `pid`; Linux queda para B0.
- **Hilo despachador** `cimenta-despachador-analisis`, `daemon=True`, único dueño del estado (`cola: deque[TrabajoAnalisis]`, `en_curso: tuple[TrabajoAnalisis, Future] | None`), con un `threading.Condition`. Cada vuelta, en este orden:
  1. Si no hay nada en curso y la cola no está vacía: saca el primero; `contenido = leer_contenido(archivo_id)`; si lanza, `seguimiento.interrumpir(id, ARCHIVO_ILEGIBLE)` y sigue. Si no, `futuro = grupo.submit(trabajo, id, contenido, dict(insumos))`. **Nunca hay más de un trabajo en el grupo.**
  2. Espera con `concurrent.futures.wait([futuro], timeout=intervalo)` si hay algo en curso, o con `condition.wait(timeout=intervalo)` si no.
  3. Vacía `cola_avance` sin bloquear, resume con `resumir_avances` (por importación, el de mayor `hojas_leidas`) y llama a `seguimiento.avanzar` una vez por importación.
  4. Si hay identificadores en curso o en cola, llama a `seguimiento.latir` con todos e incrementa el contador de latidos. Un ciclo sin identificadores no cuenta.
  5. Si el futuro terminó: con resultado, `seguimiento.terminar`. Con `BrokenProcessPool`, `seguimiento.interrumpir(id, TRABAJADOR_TERMINADO)`, `grupo.shutdown(wait=False, cancel_futures=True)` y un grupo y una cola nuevos. Con cualquier otra excepción, `seguimiento.interrumpir(id, EXCEPCION)`.
  6. Cada fallo del paso 5 y cualquier excepción de `seguimiento` se registran con `structlog` (`analisis_interrumpido`, `importacion_id`, `motivo`) y el bucle **no muere**: si `terminar` o `interrumpir` fallan contra la base, la importación sale de la lista, deja de latir y la recoge el siguiente barrido.
- **`esperar_latidos(minimo, espera_maxima)`** espera a que se emitan al menos `minimo` latidos **contados desde la llamada**; solo cuentan los que llevaron identificadores. Devuelve `False` si vence `espera_maxima`. **`esperar_inactivo`** espera a que la cola esté vacía y nada en curso.
- **`ejecutar_en_trabajador(importacion_id, contenido, insumos)`**, de nivel de módulo: `analizar_contenido(contenido, insumos, al_avanzar=lambda leidas, totales: notificar_avance(importacion_id, leidas, totales))`. **`notificar_avance`**, en el hijo: `put_nowait` en la cola global; sin cola, no hace nada.
- **`cerrar`** marca el cierre, despierta el hilo, lo espera hasta `espera_maxima` y ejecuta `grupo.shutdown(wait=False, cancel_futures=True)`. La importación en curso y las encoladas **quedan `ANALIZANDO` con su latido detenido**: las recoge el barrido del siguiente arranque.
- **`trabajo`** es inyectable para las pruebas (`soporte_tkt015.trabajo_de_prueba`).

E-9 (ejecutado el 2026-11-03 por el revisor): ENITI en el hijo, 0.70 s en frío y 0.34 s en caliente.

#### Lector (b)

`leer_libro_presupuesto(contenido: bytes, insumos_existentes: Mapping[str, str], *, al_avanzar: Callable[[int, int], None] | None = None) -> AnalisisDelLibro`. El bucle de `lector_catalogo.py:124-132` recorre **todas** las hojas, incluida la del catálogo, que salta con `continue`. La regla exacta, con `total = len(libro.sheetnames)`:

1. Un contador empieza en 0.
2. Si `catalogo.hoja is not None`, tras leer el catálogo se llama `al_avanzar(1, total)` y el contador queda en 1.
3. En el bucle, cuando `nombre == catalogo.hoja` se omite la llamada (y la hoja, como hoy). En cualquier otra hoja —sea o no de APU, y también si no es `ReadOnlyWorksheet`— se incrementa el contador y se llama `al_avanzar(contador, total)` después de procesarla.
4. Si `catalogo.hoja is None`, no hay llamada previa: todas las hojas se cuentan desde 1.
5. Si el libro no abre, no se llama nunca. Con `al_avanzar is None`, nada cambia. Ninguna otra línea cambia.

Así, un libro de cuatro hojas da siempre `(1, 4)`, `(2, 4)`, `(3, 4)` y `(4, 4)`, esté el catálogo donde esté; sin catálogo y con tres hojas, `(1, 3)`, `(2, 3)` y `(3, 3)`.

`tests/test_tkt014_lector.py:143-146` (la prueba de firma de TKT-014) fija la firma en `("contenido", "insumos_existentes")` y se pone roja. B3 la actualiza —la edita `tester-backend`— a `("contenido", "insumos_existentes", "al_avanzar")`, con `al_avanzar` solo por nombre y `None` por omisión, y **conserva** la comprobación de `:148-158` de que el módulo no importa `sqlalchemy` ni `psycopg`. La prueba de una sola apertura de TKT-014 no se toca.

#### Barrido reutilizable (b)

`backend/trabajos/barrido.py`:

```python
@dataclass(frozen=True, slots=True)
class DefinicionBarrido:
    nombre: str                    # "importacion", "archivo"
    tabla: str
    estado_intermedio: str         # ANALIZANDO · PENDIENTE
    estado_vencido: str            # CON_ERRORES · CADUCADO
    columna_marca: str             # latido · creado_en
    umbral: timedelta
    al_vencer: Callable[[Session, tuple[UUID, ...]], None]
    columna_id: str = "id"
    columna_estado: str = "estado"
```

| Firma | Qué hace |
|---|---|
| `barrer(sesion_bd: Session, definicion: DefinicionBarrido) -> tuple[UUID, ...]` | Construye `sqlalchemy.table(definicion.tabla, column(id), column(estado), column(marca))` —identificadores citados, nunca concatenados— y ejecuta `update(t).where(t.c[estado] == intermedio, or_(t.c[marca].is_(None), t.c[marca] < func.now() - umbral)).values({estado: vencido}).returning(t.c[id])`. Si devuelve filas, llama a `al_vencer(sesion_bd, ids)` en la misma sesión. No confirma |
| `barrer_todas(fabrica_sesiones: sessionmaker[Session], definiciones: Sequence[DefinicionBarrido]) -> dict[str, int]` | Una transacción por definición; devuelve `{nombre: cuenta}`. No registra: lo hace `servidor/fabrica.py`, para que el paquete no dependa de `structlog`. Una excepción se propaga |

E-8 (ejecutado el 2026-11-03 por el revisor) confirmó que psycopg enlaza `timedelta` como `interval`. El paquete importa `sqlalchemy` y la biblioteca estándar; nunca `cimenta`, `servidor`, `fastapi` ni `structlog`.

`definicion_barrido_importacion(umbral)` = `DefinicionBarrido(nombre="importacion", tabla="importacion", estado_intermedio="ANALIZANDO", estado_vencido="CON_ERRORES", columna_marca="latido", umbral=umbral, al_vencer=_al_vencer)`; `_al_vencer(sesion_bd, ids)` llama a `repositorio.insertar_errores(sesion_bd, id, [error_de_interrupcion(REINICIO)])` por cada uno. Latido nulo es vencido (`PA-15.5`).

**Tiempos en el barrido.** En la prueba de dos barridos (TC-43 y TC-43b), el segundo espera el bloqueo del primero; si el primero tardara más de 5 s, recibiría `55P03`. Los dos hilos confirman en cuanto termina su `UPDATE`, sin trabajo entre medias, y las pruebas tratan un `55P03` como fallo.

**Contratos en `pyproject.toml`:**

```toml
root_packages = ["cimenta", "tipos_base", "trabajos"]

[[tool.importlinter.contracts]]
id = "trabajos-solo-sqlalchemy"
name = "trabajos solo importa la biblioteca estándar y sqlalchemy, ni directa ni indirectamente"
type = "lista_blanca"
origen = ["trabajos"]
permitidos = ["sqlalchemy"]
broken_contract_guidance = "El barrido recibe definiciones y no conoce a quien las define (ADR-037). No se arregla con una excepción en el contrato."
```

**Por qué lista blanca y no `forbidden`.** Un `forbidden` contra `cimenta` y `servidor` dejaría pasar `fastapi`, `structlog` o cualquier tercero. La lista blanca (`herramientas.contrato_lista_blanca.ContratoListaBlanca`, la de `dominio-sin-framework` y `tipos-base-puro`) admite solo la biblioteca estándar y lo nombrado. E-7 lo comprueba. `"trabajos.*"` entra en el bloque estricto de mypy. Los contratos existentes no cambian. «15 kept» pasa a «16 kept».

**Pruebas de fronteras que hay que tocar en B1** (las edita `tester-backend`):

| Archivo y línea | Qué cambia |
|---|---|
| `tests/test_fronteras_dominio.py:38-41`, `tests/test_tkt005_fronteras.py:62-64`, `tests/test_tkt007_fronteras.py:52-54` | Copian el árbol con la tupla `("cimenta", "tipos_base", "herramientas")`; sin `"trabajos"`, `lint-imports` falla con `Could not find package trabajos`. Se añade `"trabajos"` |
| `tests/test_fronteras_dominio.py:94` y `:260`, `tests/test_tkt005_fronteras.py:161`, `tests/test_tkt007_fronteras.py:282` | `(15, 0)` pasa a `(16, 0)` |
| `tests/test_tkt013_regresion.py:29` | El literal «Contracts: 15 kept» dentro de un `or` pasa por «0 broken», pero queda obsoleto: pasa a «Contracts: 16 kept» |
| `tests/test_fronteras_dominio.py:7` | «quince contratos» (en letra) pasa a «dieciséis contratos» |
| `tests/test_fronteras_dominio.py:83` y `:256`, `tests/test_tkt005_fronteras.py:155` | «15 contratos» pasa a «16 contratos» |

#### Arranque (b)

`AjustesServidor` gana, en este orden:

| Campo | Variable | Omisión | Validación |
|---|---|---|---|
| `trabajos_intervalo_latido: int` | `CIMENTA_TRABAJOS_INTERVALO_LATIDO` | `5` segundos | `field_validator`: entre 1 y 60 |
| `trabajos_umbral_vencimiento: int` | `CIMENTA_TRABAJOS_UMBRAL_VENCIMIENTO` | `60` segundos | `field_validator` con `ValidationInfo.data`: al menos `3 × trabajos_intervalo_latido` |

Un `model_validator` daría un error con `loc` vacía, y `_mensaje` lee `e["loc"][0]`: por eso ambos son `field_validator`. **El del umbral tolera que el intervalo ya haya fallado**: si la clave no está en `info.data`, devuelve el umbral sin comparar; nunca lanza `KeyError`. `tests/test_tkt057_arranque.py:112-113` afirma que los campos son exactamente `{"db_contrasena_aplicacion", "almacen_origen"}`: B5 la actualiza (`tester-backend`) a los cuatro, conservando la comprobación de que ninguna contraseña de migración ni de lectura tiene campo.

`crear_aplicacion` gana `leer_contenido_archivo: Callable[[UUID], bytes] | None = None`; sin él usa `leer_contenido_no_configurado`, que lanza `RuntimeError("el almacén de archivos no está configurado")` y lleva la importación a `ARCHIVO_ILEGIBLE` hasta TKT-059. Hoy ninguna ruta encola análisis.

**Invariante que el arranque no puede romper.** `servidor/fabrica.py:1-8` documenta que construir la aplicación no exige variables de base ni abre conexión, y `herramientas/conexion.py` lanza `RuntimeError` si falta `CIMENTA_DB_HOST`, `CIMENTA_DB_PUERTO` o `CIMENTA_DB_NOMBRE`. Tres pruebas levantan un servidor real sin esas variables y esperan `200` en `/openapi.json`: `tests/test_servidor_arranque.py:320-350` (TC-79 de TKT-005, `fastapi dev`), `:353-405` (`test_tkt006_car4_fastapi_dev_sin_variables_de_base_publica_identidad`, invariante CA-R4 y D-2 de TKT-006) y `:408-471` (`uvicorn` real con `tests/aplicacion_con_secreto.py`). Por eso el `lifespan` distingue dos casos (P16, vía a):

- **Base configurada** si se pasó `motor`, o si `variables_de_base_presentes(entorno_efectivo)` es `True`, donde `entorno_efectivo = os.environ if entorno is None else entorno` es el mismo `Mapping` que `crear_aplicacion` (parámetro en `fabrica.py:34`, paso a `montar_identidad` en `:61`). Consultar el `entorno` recibido y no `os.environ` hace que TC-65 sea determinista con un mapa de prueba. `variables_de_base_presentes` devuelve `True` si y solo si las tres variables existen en el mapa y no están vacías. Con base configurada, el barrido es obligatorio y un fallo impide arrancar (P11).
- **Sin base configurada**, el `lifespan` no barre ni crea el ejecutor: escribe un aviso `trabajos_omitidos` con `motivo="sin variables de base"` y deja `aplicacion.state.ejecutor_analisis = None`. TKT-018 trata el `None` en su dependencia.

**El proveedor del motor se comparte.** Hoy es una expresión en línea dentro de la llamada a `montar_identidad(...)` (`fabrica.py:51-61`): `(lambda: motor) if motor is not None else functools.cache(functools.partial(crear_motor_aplicacion, contraseña))`. B5 la extrae a una variable local `proveedor_motor` antes de `montar_identidad`, y la usan identidad y el `lifespan`. Así no hay dos motores. `crear_motor_aplicacion` sigue leyendo el destino de `os.environ`: si un `entorno` de prueba dice que hay base y el proceso no la tiene, el barrido falla y la aplicación no arranca, que es lo que pide P11.

`FastAPI(..., lifespan=_ciclo_de_vida)`, con `_ciclo_de_vida` un `@asynccontextmanager` construido dentro de `crear_aplicacion`:

1. Sin base configurada: el aviso, `aplicacion.state.ejecutor_analisis = None`, `yield` y fin.
2. Con base: `fabrica_sesiones = sessionmaker(bind=proveedor_motor(), expire_on_commit=False)`; `cuentas = await run_in_threadpool(barrer_todas, fabrica_sesiones, [definicion_barrido_importacion(timedelta(seconds=umbral))])`; registro `barrido` con las cuentas.
3. `aplicacion.state.ejecutor_analisis = crear_ejecutor_analisis(fabrica_sesiones, leer_contenido, timedelta(seconds=intervalo))`.
4. `yield`.
5. `await run_in_threadpool(aplicacion.state.ejecutor_analisis.cerrar)`.

`run_in_threadpool` se importa de `fastapi.concurrency` (E-10, ejecutado el 2026-11-03 por el revisor). **El `lifespan` es la única corrutina del backend**: Starlette solo admite un gestor asíncrono, y el cuerpo no hace nada más que delegar al grupo de hilos (P13). El barrido corre **antes** de crear el ejecutor y antes de servir.

`interfaz.py` de `presupuesto` declara `__all__`, como `cimenta/auditoria/interfaz.py`: `servidor.*` está en el bloque estricto de mypy con `implicit_reexport = false`. `crear_ejecutor_analisis(fabrica_sesiones, leer_contenido, intervalo) -> EjecutorAnalisis` arma `EjecutorAnalisis(seguimiento=SeguimientoImportacion(fabrica_sesiones), ...)`. El docstring de `fabrica.py` deja de decir que solo monta `api`, nombra `cimenta.presupuesto.interfaz` y `trabajos.barrido`, y conserva la garantía de arrancar sin base.

## Experimentos previos

Los ejecutados por el revisor el 2026-11-03 usaron `uv run` con Python 3.14.3, SQLAlchemy 2.1.5 y psycopg 3.3.6, en Windows. Los pendientes los ejecuta la fila indicada, con un guion en el directorio temporal de la sesión, **nunca en el repositorio**, con `uv run python <guion>` desde `backend/` y las variables `CIMENTA_CATALOGO_ENITI` y `CIMENTA_CATALOGO_UNION`. La salida se pega en `impl.md` sin datos del cliente más allá de los que ya cita la spec.

| # | Afirmación | Experimento | Resultado | Fila | Estado |
|---|---|---|---|---|---|
| E-1 | Las cifras de la tabla de la spec | Hallazgos por causa y origen, `codigos_sin_analisis`, conceptos, insumos por crear, en los dos libros | Coinciden: ENITI 48; Union 8,608 `REF_ROTA` y 31 `SIN_APU`, 8,639 en total; ninguna celda con dos hallazgos; `ANALISIS_SIN_CODIGO` y `CODIGO_EN_VARIAS_HOJAS` con hoja del APU, fila 12, columna `C`. ENITI rechaza 23 de 24 análisis | A0 lo reconfirma con el guion | Ejecutado el 2026-11-03 por el revisor |
| E-2 | `pickle` conserva `AnalisisDelLibro`, `ErrorImportacion` y `ResultadoAnalisis` | Ida y vuelta e igualdad | Iguales; 813 KB ENITI y 707 KB Union | — | Ejecutado el 2026-11-03 por el revisor |
| E-3 | Tamaño de la preparación | `len(json.dumps(...))` de ENITI y Union (A5); `pg_column_size` y `length(preparacion::text)` (A6) | Menos de 20 MB en `pg_column_size` | A5 y A6 | `(sin ejecutar)` |
| E-4 | Cada sentencia del cierre cabe holgada en `statement_timeout = 15s` | Con Union y ENITI y `log_min_duration_statement = 0`: el `UPDATE` de `cerrar_analisis`, la sentencia más larga de `insertar_errores` y la transacción de `registrar_resultado` | Cada sentencia por debajo de 5 s; la transacción, por debajo de 10 s. **Si una sentencia pasa de 5 s, `/sdd-escalar`** | A6 y A7 | `(sin ejecutar)` |
| E-5 | La `Queue` por `initargs` con `spawn` llega al hijo | Tres mensajes del hijo al padre | En Windows: tres en orden; por `submit` falla con `RuntimeError`. **Linux pendiente** | B0 (Linux) | Windows ejecutado el 2026-11-03 por el revisor |
| E-6 | `os._exit(1)` da `BrokenProcessPool` y un grupo nuevo funciona | — | `BrokenProcessPool`; grupo nuevo con otro `pid` | — | Ejecutado el 2026-11-03 por el revisor (Windows) |
| E-7 | `trabajos` como paquete raíz con la lista blanca no rompe nada, y la lista blanca muerde | `lint-imports` antes y después; con `import structlog` y con `import cimenta` en `trabajos/__init__.py`, uno cada vez | «15 kept, 0 broken» antes, «16 kept, 0 broken» después; con cada importación deliberada, el contrato roto. **Si la lista blanca no admite un paquete raíz como origen, `/sdd-escalar` antes de B1** | B0 | `(sin ejecutar)` |
| E-8 | `timedelta` como `interval`, `GREATEST`/`COALESCE`, y el `CHECK` sobre la fila nueva | — | Pasan; `ANALIZANDO` con preparación da `23514` | — | Ejecutado el 2026-11-03 por el revisor |
| E-9 | Tiempo de ENITI en el hijo | — | 0.70 s en frío, 0.34 s en caliente | — | Ejecutado el 2026-11-03 por el revisor |
| E-10 | `run_in_threadpool` se importa de `fastapi.concurrency` | — | Importa | — | Ejecutado el 2026-11-03 por el revisor |

## Orden de implementación

Se ejecuta fila por fila con el ciclo TDD de [metodología §16](../../metodologia.md#16--el-ciclo-tdd): rojo, verde, refactor. La verificación de cada paso corre **antes** de pasar al siguiente. Todas las órdenes, desde `backend/`; las que llevan varios archivos los nombran uno por uno (PowerShell no expande comodines).

### Entrega TKT-015a · escenarios, clasificación, preparación y caso de uso síncrono

| # | Paso | Tests que pone en verde | Agente | Modelo | Verificación | Estado |
|---|---|---|---|---|---|---|
| A-pre | Escenarios 28 y 29 de HDU-001 (P15, aprobada) con todos sus efectos (ver «Escenarios 28 y 29»). Sin código | — | `desarrollador-dominio`, que carga `conv-documentacion` | `haiku` | `python tools/verificar_docs.py`; `python tools/verificar_escenarios.py` (los dos escenarios nuevos aparecen sin test, esperado hasta A1 para el escenario 29 y hasta A2a para el 28; se anota en `impl.md`); `python -m unittest discover -s tools/tests -v` | Pendiente |
| A0 | Reconfirmar E-1 con el guion; salida en `impl.md` | — | `tester-backend` | `haiku` · tarea mecánica | Coincide con E-1. **Si no, `/sdd-escalar` antes de A1** | Pendiente |
| A1 | `dominio/importacion.py` sin `progreso_de_lectura`. El tester crea `herramientas/soporte_tkt015.py` con los ayudantes en memoria. ~90 líneas | TC-01 a TC-04 | `desarrollador-dominio` | `haiku` | `uv run pytest tests/test_tkt015_importacion.py`; `uv run python -m herramientas.verificar_float` | Pendiente |
| A2a | `clasificacion_importacion.py`, parte 1: `TIPO_POR_CAUSA`, plantillas, `_enumerar`, `clasificar_hallazgo`, `es_celda_de_rendimiento`. ~120 líneas | TC-05 a TC-09 | `desarrollador-dominio` | `haiku` | `uv run pytest tests/test_tkt015_clasificacion.py`; `uv run lint-imports` | Pendiente |
| A2b | `clasificacion_importacion.py`, parte 2: `errores_sin_apu`, `detectar_duplicados`, `clasificar_libro` con `filas_rechazadas` y `hojas_rechazadas`. ~90 líneas | TC-10 a TC-15 | `desarrollador-dominio` | `haiku` | `uv run pytest tests/test_tkt015_clasificacion_libro.py tests/test_tkt015_clasificacion.py` | Pendiente |
| A3 | `dominio/preparacion_importacion.py`. ~70 líneas | TC-16 | `desarrollador-dominio` | `haiku` | `uv run pytest tests/test_tkt015_preparacion.py`; `uv run mypy .` | Pendiente |
| A4 | Migración `v0009` con su docstring y plan de reversa. El tester actualiza antes, en el rojo, `tests/test_tkt011_linea_base.py` (`COLUMNAS_ESPERADAS["importacion"]` gana la fila de `preparacion`, `jsonb`, anulable) y `tests/test_tkt011_migracion_linea_base.py` (el conjunto de `CHECK` de `importacion` gana `ck_importacion_preparacion_tras_analisis`), sin relajar ninguna otra aserción. ~45 líneas de producción y ~10 de pruebas existentes | TC-17, TC-18 | `desarrollador-sql` | `haiku` | `uv run --env-file ../.env alembic upgrade head`, `downgrade -1`, `upgrade head`; `uv run pytest tests/test_tkt015_esquema.py tests/test_tkt011_linea_base.py tests/test_tkt011_migracion_linea_base.py` | Pendiente |
| A5 | `infraestructura/tablas.py`, `preparacion_json.py`, `trabajo_analisis.py`; E-3 (texto). El tester añade `libro_sintetico` a `soporte_tkt015.py`. ~150 líneas | TC-19 a TC-23 | `desarrollador-aplicacion` (carga `conv-backend-fastapi`) | `haiku` | `uv run pytest tests/test_tkt015_contenido.py`; E-3 en `impl.md`. **Riesgo:** una preparación tan grande que su `UPDATE` se acerque al `statement_timeout`; lo mide E-4 en A6 | Pendiente |
| A6 | `repositorio_importacion.py` (parte a) y `aplicacion/analisis_importacion.py` (`iniciar_analisis`, `registrar_resultado`, `registrar_interrupcion`, `obtener_preparacion`); E-3 (base) y E-4. ~200 líneas | TC-24 a TC-39 | `desarrollador-aplicacion` | `sonnet` · disparador: bloqueo pesimista y concurrencia (`FOR UPDATE` y TC-35) | `uv run pytest tests/test_tkt015_analisis.py tests/test_tkt015_esquema.py`; E-3 y E-4 en `impl.md`. **Riesgo:** `lock_timeout` de 5 s y `statement_timeout` de 15 s: una sentencia de más de 5 s detiene la fila | Pendiente |
| A7 | El tester escribe `tests/test_tkt015_archivos_reales.py`; E-4 con Union. Sin código de producción | TC-40, TC-41, TC-42, TC-INV-1 | `tester-backend` | `sonnet` · valor por omisión del agente | `uv run pytest tests/test_tkt015_archivos_reales.py tests/test_tkt013_archivos_reales.py tests/test_tkt014_archivos_reales.py -ra`. Sin las variables, `SKIPPED` con motivo; **con ellas, en verde**. **Si una cifra difiere, `/sdd-escalar`** | Pendiente |
| A8 | ADR-036 y documentación de a. Sin código | — | `desarrollador-dominio`, que carga `conv-documentacion` | `haiku` | `python tools/verificar_docs.py`; `python tools/extraer_mermaid.py`; `python -m unittest discover -s tools/tests -v`; `Grep` del conteo de ADR, salida en `impl.md` | Pendiente |
| A9 | Cierre de a: mutantes M-01 a M-12; `CA-R2` | Todos los de a, TC-INV-1 y TC-INV-2 | `tester-backend` | `sonnet` · valor por omisión del agente | Cada mutante en rojo y revertido; TC-INV-2: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy .`, `uv run lint-imports`, `uv run python -m herramientas.verificar_float`; `uv run pytest`; `python tools/verificar_escenarios.py` sin escenarios huérfanos de HDU-001 | Pendiente |

### Entrega TKT-015b · trabajo en proceso aparte, latido y barrido

| # | Paso | Tests que pone en verde | Agente | Modelo | Verificación | Estado |
|---|---|---|---|---|---|---|
| B0 | E-5 en Linux (contenedor de CI o imagen `python:3.14`) y E-7; salida en `impl.md` | — | `tester-backend` | `haiku` · tarea mecánica | Lo esperado. **Si E-5 falla en Linux, `/sdd-escalar` antes de B4**; si E-7 falla, antes de B1 | Pendiente |
| B1 | `trabajos/barrido.py`; contrato, `root_packages` y mypy en `backend/pyproject.toml`. El tester actualiza antes las tres suites de fronteras (tabla de B1). ~90 líneas de producción y ~15 de pruebas existentes | TC-43, TC-44, TC-45 y las tres suites de fronteras | `desarrollador-aplicacion` | `sonnet` · disparador: concurrencia (dos barridos simultáneos) | `uv run pytest tests/test_tkt015_barrido.py tests/test_fronteras_dominio.py tests/test_tkt005_fronteras.py tests/test_tkt007_fronteras.py`; `uv run lint-imports` con «16 kept, 0 broken» (`CA-R2`); `uv run mypy .`. **Riesgo:** `lock_timeout` en TC-43 | Pendiente |
| B1b | `--cov=trabajos` en el paso de pruebas del trabajo `backend` de `.github/workflows/ci.yml`, y un **caso nuevo e independiente** en `tools/tests/test_definicion_ci.py` que lea el `ci.yml` real y afirme `--cov=trabajos`. `comprobar_tc01` (`:282-304`) no se toca: sus fixtures sintéticos (`:567`, `:660`, `:2336`) solo llevan `--cov=cimenta` y se pondrían rojos. ~25 líneas | `tools/tests/test_definicion_ci.py` | `ingeniero-devsecops` | `sonnet` · valor por omisión del agente: compuerta del pipeline | `python -m unittest discover -s tools/tests -v`; `uv run pytest --cov=cimenta --cov=tipos_base --cov=contrato_error --cov=servidor --cov=trabajos`, informe de `trabajos` en `impl.md` | Pendiente |
| B2 | `aplicacion/barrido_importacion.py` y su exportación en `interfaz.py`. ~35 líneas | TC-43b, TC-46 a TC-49 | `desarrollador-aplicacion` | `haiku` | `uv run pytest tests/test_tkt015_barrido_importacion.py tests/test_tkt015_barrido.py` | Pendiente |
| B3 | `al_avanzar` en `leer_libro_presupuesto` y en `analizar_contenido`; `progreso_de_lectura`. El tester actualiza antes la prueba de firma de TKT-014 (`tests/test_tkt014_lector.py:143-146`) y conserva `:148-158`. ~30 líneas | TC-50, TC-51, TC-INV-3 y la prueba de firma de TKT-014 | `desarrollador-dominio` | `haiku` | `uv run pytest tests/test_tkt015_avance.py tests/test_tkt014_lector.py tests/test_tkt013_lector.py tests/test_tkt015_contenido.py` | Pendiente |
| B4 | `repositorio_importacion.py` (parte b), `ejecutor_analisis.py`, `SeguimientoImportacion`, `solicitar_analisis`; el tester añade `trabajo_de_prueba` y `liberar` a `soporte_tkt015.py`. ~250 líneas | TC-52 a TC-62 | `desarrollador-aplicacion` | `sonnet` · disparador: concurrencia (hilo, procesos, cola compartida) | `uv run pytest tests/test_tkt015_ejecutor.py` **tres veces seguidas** sin fallo intermitente, salida en `impl.md` | Pendiente |
| B5 | Ajustes (validador tolerante), `variables_de_base_presentes`, extracción de `proveedor_motor`, `lifespan` con sus dos casos, `crear_ejecutor_analisis`, `leer_contenido_no_configurado` y `__all__`. El tester actualiza antes `tests/test_tkt057_arranque.py:112-113`. ~90 líneas | TC-63 a TC-67 y `test_tkt057_arranque.py` actualizado | `desarrollador-aplicacion` | `sonnet` · corrutina única con `asynccontextmanager`, mypy estricto en `servidor.*`, el invariante de P16 y tres pruebas con servidor real | `uv run pytest tests/test_tkt015_arranque.py tests/test_servidor_arranque.py tests/test_tkt057_arranque.py tests/test_tkt057_configuracion.py tests/test_tkt057_entorno.py tests/test_tkt006_inicio_sesion.py tests/test_tkt006_sesion_vigente.py tests/test_tkt006_cierre.py tests/test_tkt006_csrf.py tests/test_tkt006_enrutador.py tests/test_tkt006_permisos_rol.py`, `tests/test_tkt057_csrf.py`, `tests/test_tkt057_cabeceras.py`, `tests/test_tkt057_limite_intentos.py` (usan la fixture `cliente`, que ahora ejecuta el `lifespan`), con **`tests/test_servidor_arranque.py` completo**; `uv run mypy .` | Pendiente |
| B6 | ADR-037 y documentación de b. Sin código | — | `desarrollador-dominio`, que carga `conv-documentacion` | `haiku` | `python tools/verificar_docs.py`; `python tools/extraer_mermaid.py`; `python -m unittest discover -s tools/tests -v`; `Grep` del conteo de ADR | Pendiente |
| B7 | Cierre de b: mutantes M-13 a M-23; `CA-R2`; suite completa con y sin las variables de los archivos reales | Todos los de b, TC-INV-2 y la regresión completa | `tester-backend` | `sonnet` · valor por omisión del agente | Cada mutante en rojo y revertido; TC-INV-2; los trabajos `backend` y `fronteras` de `ci.yml` en verde en local | Pendiente |

**Modelo:** `haiku` por omisión. A6, B1 y B4 caen en el disparador «bloqueo pesimista o concurrencia» de [metodología §14](../../metodologia.md#14--enrutamiento-de-modelo); B5 va en `sonnet` por la corrutina única, mypy estricto y el invariante de arranque de TKT-006, que no admite un segundo intento a ciegas. Las filas de cierre y de archivos reales van en `sonnet` por el valor por omisión de `tester-backend`, y B1b por el de `ingeniero-devsecops`. Ninguna fila va en `opus`.

**Las pruebas existentes que el diseño obliga a cambiar** las cambia `tester-backend` (o `ingeniero-devsecops` en B1b), en el rojo de su fila: las dos suites de TKT-011 (A4), las tres suites de fronteras y el literal «Contracts: 15 kept» de `tests/test_tkt013_regresion.py:29` (B1), la prueba de firma de TKT-014 (B3) y `tests/test_tkt057_arranque.py:112-113` (B5). Ninguna se relaja.

Estado: `Pendiente` · `✓ Hecho` · `⚠ Ajustado` (y el ajuste se documenta en `impl.md`).

### Escenarios 28 y 29 (fila A-pre)

Se añaden a HDU-001, con el formato de sus escenarios:

- **Escenario 28 · Rendimiento ausente en un análisis.** Dado un libro cuya hoja de APU trae un insumo con la celda de rendimiento vacía, cuando se analiza, la importación queda `CON_ERRORES` con un `RENDIMIENTO_AUSENTE` en la hoja, la fila del insumo y la columna del rendimiento; **y** ninguna otra celda vacía (unidad, analista, rótulo) se reporta como `RENDIMIENTO_AUSENTE`.
- **Escenario 29 · Análisis interrumpido.** Dado un análisis que se interrumpe (reinicio del servidor, excepción o muerte del trabajador), la importación queda `CON_ERRORES` con un único `PROCESO_INTERRUMPIDO` cuyo mensaje distingue la causa, sin preparación, la obra admite otra importación y la interrumpida admite el reintento; **y** el barrido no toca una importación con latido vigente ni una que ya salió de `ANALIZANDO`.

Efectos, en el mismo cambio: la DoD de HDU-001 pasa de 27 a 29 escenarios; el total de `docs/04-historias-usuario.md:62`, de 162 a 164; `docs/06-stack-tecnologico.md:189` y `:397`; la fila «Escenarios de aceptación \| 162» de `README.md`; los `x-escenarios` de las operaciones de importación del borrador OpenAPI; y `tools/historias_activas.txt` si su forma lo exige; además `llms.txt:19` (de 162 a 164), `docs/04-historias-usuario.md:469-470` («Los 27 son de fase 1» pasa a 29) y la columna de escenarios de `docs/07-especificacion-api.md:277-279`.

## Plan de pruebas

**Regla de importación en archivos compartidos (H-7).** Donde un archivo de pruebas recibe tests de más de una fila, o donde el módulo bajo prueba todavía no existe, **los tests nuevos importan el módulo bajo prueba dentro de la función de prueba** hasta que el módulo exista: el rojo válido es un `ImportError` o un `AssertionError` dentro del test, nunca un error de recolección que tumbe los tests ya verdes del mismo archivo. Además, cada fila tiene su propio archivo cuando es natural (ver la columna «Archivo»): `test_tkt015_importacion.py` (A1), `test_tkt015_clasificacion.py` (A2a), `test_tkt015_clasificacion_libro.py` (A2b), `test_tkt015_preparacion.py` (A3), `test_tkt015_esquema.py` (A4), `test_tkt015_contenido.py` (A5), `test_tkt015_analisis.py` (A6), `test_tkt015_archivos_reales.py` (A7), `test_tkt015_barrido.py` (B1), `test_tkt015_barrido_importacion.py` (B2), `test_tkt015_avance.py` (B3), `test_tkt015_ejecutor.py` (B4), `test_tkt015_arranque.py` (B5).

**Datos.** Todo contra PostgreSQL con `alembic upgrade head` y el rol de aplicación; las filas `importacion`, `obra` y `usuario` las crea `DatosPresupuesto` de `conftest.py`. El origen de los bytes es un diccionario `archivo_id → bytes` (`PA-15.3`). Los archivos reales se omiten con `skip` y motivo si falta la variable. Todo rechazo comprueba el dato completo: tipo, hoja, fila, columna, valor original y mensaje exacto del error; en `CA-18`, la clase, el `tipo`, el `codigo`, el `mensaje`, el `detalle` y las `acciones`, **y** que la fila, sus errores y su preparación no cambiaron.

### `herramientas/soporte_tkt015.py`

Vive fuera de `tests/` (aprendizaje de TKT-013 con mypy) y no importa `conftest.py`: `LibroCatalogo` vive en `tests/conftest.py`, así que las funciones reciben el protocolo `LibroCatalogoPrueba` de `soporte_tkt013.py:56` (`nueva_hoja`, `escribir_fila`, `bytes`), como `libro_eniti_con_apu_y_resumen`. La prueba le pasa la fixture `LibroCatalogo` de `conftest.py`.

```python
type CampoConcepto = Literal["codigo", "descripcion", "unidad", "cantidad", "precio_unitario", "importe"]

def libro_sintetico(
    libro: LibroCatalogoPrueba,
    *,
    conceptos: int = 200,
    codigos: Sequence[str] = ("P-001", "P-002"),
    codigo_en: Mapping[int, str] | None = None,
    descripciones: Mapping[int, str] | None = None,
    unidad_en: Mapping[int, str] | None = None,
    rotos: Mapping[tuple[int, CampoConcepto], str] | None = None,
    hojas_apu: Sequence[str] | None = None,
    variantes_apu: Mapping[str, Mapping[str, Any]] | None = None,
    catalogo_vacio: bool = False,
    posicion_catalogo: int = 0,
) -> bytes
```

**Diseño de filas de la hoja `CATALOGO`** (cifras neutras):

| Filas | Contenido |
|---|---|
| 1 a 3 | Vacías (`(None,)`) |
| 4 | Encabezado: `("Código", "DESCRIPCION", "Unidad", "Cantidad", "P.U.", "IMPORTE")` |
| 5 a 8 | Títulos de la jerarquía: `(None, "RAIZ SINTETICA")`, `(None, "NIVEL 1")`, `(None, "ZONA A")`, `(None, "PARTIDA MUROS")` — una sola partida |
| 9 a `8 + conceptos` | Un concepto por fila |

Por cada fila de concepto `r`: `codigo = codigo_en.get(r, codigos[(r - 9) % len(codigos)])`; `descripcion = descripciones.get(r, f"CONCEPTO {codigo}")` —**la misma descripción para el mismo código por omisión**, para no disparar `DUPLICADO` por accidente—; `unidad = unidad_en.get(r, "M2")`; `cantidad = 1`, `precio_unitario = 10`, `importe = 10` (enteros). `rotos[(r, campo)]` sustituye la celda de ese campo por la cadena dada, tal cual (por ejemplo `"#REF!"`). Con este diseño, las filas 12, 45, 57 y 90 que piden `CA-5` y `CA-7` son filas de concepto.

**Hojas de APU.** Con `hojas_apu=None`, una hoja por código distinto del catálogo, en orden de primera aparición, llamada `f"APU {codigo}"` y escrita con `escribir_hoja_apu_sintetica(libro, nombre, codigo=codigo, **variantes_apu.get(codigo, {}))` (código en la fila 2, columna `C`; pie que cuadra en `158.93`). Con una secuencia, solo esos códigos. `variantes_apu` pasa los argumentos de `hoja_apu_sintetica` (`celdas_rotas`, `siroc`…). `catalogo_vacio=True` crea la hoja `CATALOGO` sin escribir nada. `posicion_catalogo` es el índice de la hoja del catálogo en el libro (0, la primera).

**Ejemplos de llamada:**

| TC | Llamada |
|---|---|
| TC-19, TC-24, TC-31 | `libro_sintetico(libro, conceptos=20)` |
| TC-20, TC-25 | `libro_sintetico(libro, rotos={(f, c): "#REF!" for f in (20, 30, 40) for c in ("precio_unitario", "importe")})` |
| TC-26 | `libro_sintetico(libro, conceptos=3, codigos=("P-001", "P-002", "P-003"), hojas_apu=("P-001", "P-002"))` |
| TC-27 | `libro_sintetico(libro, unidad_en={57: "XYZ"})` |
| TC-28 | `libro_sintetico(libro, conceptos=20, variantes_apu={"P-001": {"celdas_rotas": {(8, "F"): None}}})` (fila 8, columna `F`: rendimiento de `MATERIAL UNO`) |
| TC-29 | `libro_sintetico(libro, codigo_en={12: "620001", 45: "620001", 90: "620001"}, descripciones={12: "MURO STD", 45: "MURO STD", 90: "PLAFON"})` |
| TC-30 | `libro_sintetico(libro, conceptos=0)` y `libro_sintetico(libro, catalogo_vacio=True)` |
| TC-50 | `libro_sintetico(libro, conceptos=3, codigos=("P-001", "P-002", "P-003"))` (cuatro hojas) y lo mismo con `posicion_catalogo=2` |

**Ayudantes en memoria** (A1, A2a y A2b): `hallazgo(causa, hoja="CATALOGO", fila=57, columna="F", valor="#REF!", detalle=None) -> Hallazgo` y `catalogo_en_memoria(filas: Sequence[tuple[int, str, str | None]]) -> CatalogoLeido` (fila, código, descripción), reutilizando `catalogo_con_codigos` de `soporte_tkt014` donde baste.

**Trabajo de prueba** (B4): `trabajo_de_prueba(importacion_id: UUID, contenido: bytes, insumos: Mapping[str, str]) -> ResultadoAnalisis`, de nivel de módulo, interpreta `contenido.decode()` como orden: `anotar` (devuelve sin errores una preparación `{"formato": 1, "pid", "inicio", "fin"}`); `bloquear:<ruta>` (anota el inicio, espera a que exista el archivo `<ruta>` sondeando cada 10 ms, con tope de 30 s, y devuelve como `anotar`); `morir:<ruta>` (espera igual y `os._exit(1)`); `fallar` (`ValueError("fallo de prueba")`); `avance:<ruta>` (`notificar_avance` con `(1, 5)` y `(3, 5)` y después bloquea); `avance-desordenado:<ruta>` (`(3, 5)` y después `(1, 5)`, y bloquea). `liberar(ruta: Path) -> None` crea el archivo. El sondeo vive en el hijo; **las pruebas nunca usan `sleep`**: esperan con `esperar_latidos` y `esperar_inactivo`, con tope de 30 s.

### TKT-015a · dominio

| # | Caso | Tipo | Criterio | Archivo · fila |
|---|---|---|---|---|
| TC-01 | `test_hdu001_esc04_estado_tras_analisis`: `()` → `VALIDADO`; un solo `SIN_APU` → `CON_ERRORES` | feliz y **rechazo** | `CA-1`, `CA-4`, `M2` | `importacion` · A1 |
| TC-02 | `test_tkt015_estados_que_admiten_analisis`: parametrizada; solo `RECIBIDO` y `CON_ERRORES` con `{PROCESO_INTERRUMPIDO}` dan `True`; `CON_ERRORES` con `{PROCESO_INTERRUMPIDO, REF_ROTA}`, con `{REF_ROTA}` o sin errores, y `ANALIZANDO`, `VALIDADO`, `CONFIRMADO` y `DESCARTADO`, `False` | **rechazo** | `CA-18` | `importacion` · A1 |
| TC-03 | `test_hdu001_esc29_mensajes_de_interrupcion_distinguen_la_causa`: los cuatro motivos dan `PROCESO_INTERRUMPIDO`, ubicación y valor nulos y los cuatro mensajes exactos de la tabla, distintos | **rechazo** | `CA-14`, `CA-15` | `importacion` · A1 |
| TC-04 | `test_tkt015_mapa_de_insumos_existentes`: `[(" canal  x ", "PZA"), ("CANAL X", "KG")]` → `{"CANAL X": "PZA"}` | borde | `CA-1` | `importacion` · A1 |
| TC-05 | `test_hdu001_esc06_toda_causa_tiene_tipo_y_mensaje`: `set(TIPO_POR_CAUSA) == set(CausaHallazgo)` y lo mismo con las plantillas; parametrizada por cada causa: un `Hallazgo` da un `ErrorImportacion` de uno de los siete tipos con `mensaje.endswith(f" (causa: {causa})")` y la ubicación según la regla 2; las causas `SIN_CONCEPTOS` son exactamente las cinco de hoja; `CONCEPTO_SIN_PARTIDA`, `PROFUNDIDAD_EXCEDIDA` y `CODIGO_SIN_CONCEPTO` dan `REF_ROTA` con su ubicación; un hallazgo con ubicación nula (`VALOR_AUSENTE` con `detalle="sin rótulo «fecha» en la cabecera"`) da `REF_ROTA` con ubicación nula y el mensaje con el detalle. Una causa nueva sin destino la pone roja | **rechazo** | `CA-10`, `M1` | `clasificacion` · A2a |
| TC-06 | `test_hdu001_esc06_ref_rota_conserva_la_celda`: `ERROR_DE_FORMULA` en `("CATALOGO", 57, "F", "#REF!")` → `REF_ROTA` con esas cuatro y el mensaje exacto de la fila 6, sin hoja ni fila en el texto | **rechazo** | `CA-2` | `clasificacion` · A2a |
| TC-07 | `test_hdu001_esc08_unidad_desconocida`: `UNIDAD_NO_RECONOCIDA` en la fila 57, columna de la unidad, `"XYZ"` → `UNIDAD_DESCONOCIDA` con el mensaje exacto | **rechazo** | `CA-5` | `clasificacion` · A2a |
| TC-08 | `test_hdu001_esc28_rendimiento_ausente_solo_en_la_celda_de_rendimiento`: `leer_apu_en_memoria` con el rendimiento vacío → `RENDIMIENTO_AUSENTE` con hoja, fila del insumo y `F`; en el mismo análisis, unidad vacía (`D`), analista vacío (`B`) y base de cargo vacía (`E`) → `REF_ROTA`; `VALOR_AUSENTE` del catálogo en `F` → `REF_ROTA`; `NO_ES_NUMERO` en el rendimiento → `REF_ROTA` | **rechazo** | `CA-6` | `clasificacion` · A2a |
| TC-09 | `test_hdu001_esc27_hoja_sin_conceptos`: `NINGUN_CONCEPTO` (fila 5) y `ENCABEZADO_NO_LOCALIZADO` (columna `A`) → `SIN_CONCEPTOS` con la hoja, fila y columna nulas y el mensaje exacto, que contiene la hoja, la fila del encabezado (en el primero) y `ESTRUCTURA_MINIMA_DEL_CATALOGO` | **rechazo** | `CA-9` | `clasificacion` · A2a |
| TC-10 | `test_hdu001_esc07_codigo_sin_apu`: catálogo con `P-001` (filas 10 y 20), `P-002`, `P-003` (filas 30 y 40) y `codigos_sin_analisis=("P-003",)` → un único `SIN_APU` en la fila 30, columna `A`, `valor_original="P-003"` y el mensaje exacto | **rechazo** | `CA-4` | `clasificacion_libro` · A2b |
| TC-11 | `test_hdu001_esc09_duplicado_con_descripciones_distintas`: `620001` en las filas 12 y 45 con `MURO STD` y en la 90 con `PLAFON` → un único `DUPLICADO`, fila 12, columna `A`, `valor_original="620001"` y el mensaje exacto del ejemplo de dos grupos | **rechazo** | `CA-7` | `clasificacion_libro` · A2b |
| TC-12 | `test_hdu001_esc09_misma_descripcion_normalizada_no_es_duplicado`: `" muro  std"`, `"MURO STD"`, `"Muro\tStd "` con el mismo código → ningún `DUPLICADO`; dos conceptos con código `"#REF!"` y descripciones distintas → ningún `DUPLICADO` | **rechazo** del rechazo | `CA-8` | `clasificacion_libro` · A2b |
| TC-13 | `test_hdu001_esc06_ningun_hallazgo_se_pierde`: un `AnalisisDelLibro` con dos hallazgos de catálogo, uno de análisis, uno de libro, un código sin análisis y un duplicado → seis errores en el orden declarado | **rechazo** | `CA-10` | `clasificacion_libro` · A2b |
| TC-14 | `test_tkt015_filas_y_hojas_rechazadas`: errores de fila rechazan su fila; un `SIN_APU` y un `DUPLICADO` del catálogo rechazan **todas** las filas de su código; un código con `CODIGO_EN_VARIAS_HOJAS` (dos hojas de APU) y un insumo con `TIPO_EN_CONFLICTO` rechazan **solo** sus hojas de APU, **ninguna** fila del catálogo; un `CARGO_DESCONOCIDO` rechaza su hoja | **rechazo** | `CA-11`, `CA-S1`, P3 | `clasificacion_libro` · A2b |
| TC-15 | `test_hdu001_esc09_mensaje_de_duplicado_en_espanol`: `_enumerar` con uno, dos, tres y cuatro elementos; el mensaje del ejemplo de tres grupos, exacto | borde | `CA-7` | `clasificacion_libro` · A2b |
| TC-16 | `test_hdu001_esc06_preparacion_excluye_lo_rechazado`: con la `Clasificacion` de TC-14, conceptos y análisis rechazados fuera, asociaciones de análisis rechazados fuera, nodos e insumos por crear dentro; `filas_leidas`, `filas_validas` y `filas_rechazadas` exactas | **rechazo** | `CA-11`, `CA-S1` | `preparacion` · A3 |

### TKT-015a · esquema

| # | Caso | Tipo | Criterio | Archivo · fila |
|---|---|---|---|---|
| TC-17 | `test_tkt015_migracion_0009_reversible`: `upgrade head` → `downgrade -1` (la columna y el `CHECK` desaparecen) → `upgrade head`; con el rol de aplicación, un `UPDATE` que deja `preparacion` no nula con `estado = 'ANALIZANDO'` falla con `23514` y `ck_importacion_preparacion_tras_analisis` | **rechazo** | `CA-11` | `esquema` · A4 |
| TC-18 | `test_tkt015_car3_tipos_e_invariante_13_intactos`: `TipoErrorImportacion` y `EstadoImportacion` iguales a `pg_get_constraintdef` de sus `CHECK`; `uq_concepto_obra_id_codigo` sigue siendo `UNIQUE (obra_id, codigo)` | regresión | `CA-R3` | `esquema` · A4 |

### TKT-015a · contenido, sin base

| # | Caso | Tipo | Criterio | Archivo · fila |
|---|---|---|---|---|
| TC-19 | `test_tkt015_analizar_contenido_libro_valido`: `analizar_contenido(libro_sintetico(libro, conceptos=20), {})` → `errores == ()`, `filas_leidas == 20`, `filas_validas == 20`, `preparacion["formato"] == 1`, veinte conceptos, dos análisis, dos asociaciones y tres insumos por crear | feliz | `CA-1` | `contenido` · A5 |
| TC-20 | `test_tkt015_analizar_contenido_ref_rota_197_en_preparacion`: con tres filas rotas → seis `REF_ROTA` y 197 conceptos en `preparacion["conceptos"]`, ninguno de las filas 20, 30 y 40 | **rechazo** | `CA-2`, `CA-S1` | `contenido` · A5 |
| TC-21 | `test_tkt015_preparacion_json_decimal_como_cadena_sin_cuantizar`: una `Preparacion` con `Dinero("641.3608310977561")`, `Rendimiento("0.3278")` y `Cantidad("16.089")` → `"641.3608310977561"`, `"0.3278"` y `"16.089"`, todos `str`; `json.dumps` no falla y no hay ningún `float` en el árbol | feliz | `CA-11`, regla 1 | `contenido` · A5 |
| TC-22 | `test_tkt015_preparacion_json_none_a_null`: un concepto con `descripcion=None` y `importe=None`, un nodo con `nombre=None`, un cargo con `tipo=None` y una ruta con `area=None` → `null` en cada clave de la tabla del formato | borde | `CA-11` | `contenido` · A5 |
| TC-23 | `test_tkt015_resultado_sobrevive_a_pickle`: `pickle.loads(pickle.dumps(r)) == r` para el `ResultadoAnalisis` de TC-20 | regresión | `CA-12` | `contenido` · A5 |

### TKT-015a · caso de uso

Cada prueba ejecuta `iniciar_analisis`, `analizar_contenido` y `registrar_resultado` en secuencia, salvo donde se dice otra cosa.

| # | Caso | Tipo | Criterio | Archivo · fila |
|---|---|---|---|---|
| TC-24 | `test_hdu001_esc05_libro_valido_queda_validado`: `VALIDADO`, cero errores, `progreso == 1`, preparación con `formato == 1` y su contenido; las cuentas de `concepto`, `insumo`, `linea_base`, `linea_base_concepto`, `explosion_presupuesto` y `presupuesto_control` iguales antes y después | feliz | `CA-1` | `analisis` · A6 |
| TC-25 | `test_hdu001_esc06_ref_rota_seis_errores_y_197_en_preparacion`: `CON_ERRORES`, seis `REF_ROTA` con hoja, fila, columna, mensaje y `"#REF!"`; 197 en la preparación; `filas_leidas == 200`, `filas_validas == 197`, `filas_rechazadas == 3` | **rechazo** | `CA-2`, `CA-S1` | `analisis` · A6 |
| TC-26 | `test_hdu001_esc07_sin_apu_persistido`: un `SIN_APU` con el código del tercero y el mensaje exacto | **rechazo** | `CA-4` | `analisis` · A6 |
| TC-27 | `test_hdu001_esc08_unidad_desconocida_persistida`: un `UNIDAD_DESCONOCIDA` en la fila 57 y la columna de la unidad; ninguna otra fila con error de unidad | **rechazo** | `CA-5` | `analisis` · A6 |
| TC-28 | `test_hdu001_esc28_rendimiento_ausente_persistido`: un `RENDIMIENTO_AUSENTE` con la hoja, la fila y `F`; ningún otro | **rechazo** | `CA-6` | `analisis` · A6 |
| TC-29 | `test_hdu001_esc09_duplicado_persistido`: un `DUPLICADO` con `12, 45 y 90` | **rechazo** | `CA-7` | `analisis` · A6 |
| TC-30 | `test_hdu001_esc27_sin_conceptos_persistido`: parametrizada, solo encabezados y catálogo vacío → `CON_ERRORES`, un `SIN_CONCEPTOS` con la hoja y fila y columna nulas; sin excepción | **rechazo** | `CA-9` | `analisis` · A6 |
| TC-31 | `test_hdu001_esc06_preparacion_con_dinero_en_cadena_sin_reabrir`: tras analizar, `monkeypatch` hace que `load_workbook` de `lector_catalogo` lance; `obtener_preparacion` devuelve el documento con toda cifra `str` | feliz y **rechazo** | `CA-11` esc. 1 | `analisis` · A6 |
| TC-32 | `test_hdu001_esc29_interrupcion_no_deja_preparacion`: `iniciar_analisis` y `registrar_interrupcion(EXCEPCION)` → `CON_ERRORES`, `preparacion IS NULL`, un único `PROCESO_INTERRUMPIDO` con el mensaje de `EXCEPCION` | **rechazo** | `CA-11` esc. 2 | `analisis` · A6 |
| TC-33 | `test_tkt015_estado_que_no_admite_analisis`: parametrizada por `ANALIZANDO`, `VALIDADO`, `CONFIRMADO`, `DESCARTADO` y `CON_ERRORES` con un `REF_ROTA` → `ConflictoEstado` con `tipo == "CONFLICTO"`, `codigo == ESTADO_NO_PERMITE_OPERACION`, mensaje exacto, `detalle == {"importacion_id": str(id), "estado": <estado>}` y sin acciones; fila, errores y preparación idénticos | **rechazo** | `CA-18` esc. 1 | `analisis` · A6 |
| TC-34 | `test_hdu001_esc29_reintento_tras_interrupcion`: `CON_ERRORES` con un solo `PROCESO_INTERRUMPIDO` → `iniciar_analisis` la deja `ANALIZANDO`, `progreso == 0`, latido no nulo, preparación nula, sin errores; tras `registrar_resultado`, solo los errores del intento nuevo | feliz | `CA-18` esc. 2, `CA-15` | `analisis` · A6 |
| TC-35 | `test_tkt015_dos_solicitudes_simultaneas`: dos hilos con `Barrier(2)` y dos sesiones → exactamente uno devuelve `TrabajoAnalisis` y el otro `ConflictoEstado` con `estado == "ANALIZANDO"`; un `55P03` es fallo | **concurrencia** | `CA-18` esc. 3 | `analisis` · A6 |
| TC-36 | `test_tkt015_importacion_inexistente`: `NoEncontrado` con `recurso == "importacion"` | **rechazo** | `CA-18` | `analisis` · A6 |
| TC-37 | `test_tkt015_resultado_tardio_no_pisa_el_estado`: tras `iniciar_analisis`, un `UPDATE` la pasa a `CON_ERRORES`; `registrar_resultado` devuelve `False` y no cambia nada | **rechazo** | `CA-16`, `RNF-17` | `analisis` · A6 |
| TC-38 | `test_tkt015_errores_en_lote_todo_o_nada`: 8,600 errores válidos → los 8,600 en una transacción; otro lote cuyo último error lleva `tipo="TIPO_INVALIDO"` como `str` suelto (puesto con `object.__setattr__`) → la base lo rechaza por el `CHECK`, y la importación sigue `ANALIZANDO`, con cero errores y preparación nula | **rechazo** | `CA-3`, `CA-11`, `PA-15.1` | `analisis` · A6 |
| TC-39 | `test_hdu001_esc06_cada_tipo_y_causa_persisten`: parametrizada por las 22 causas, más `SIN_APU`, `DUPLICADO` y `PROCESO_INTERRUMPIDO`: el error clasificado se persiste con `insertar_errores` y se relee igual; los siete tipos aparecen al menos una vez | **rechazo** | `CA-10` | `analisis` · A6 |

### TKT-015a · archivos reales

| # | Caso | Tipo | Criterio | Archivo · fila |
|---|---|---|---|---|
| TC-40 | `test_hdu001_esc06_union_square_fila_a_fila` (real): `CON_ERRORES` sin excepción y sin quedar `ANALIZANDO`; 8,562 `REF_ROTA` con sufijo `(causa: ERROR_DE_FORMULA)`, cada uno con hoja, fila y columna; 5 `REF_ROTA` de `CONCEPTO_SIN_PARTIDA` con su fila; 31 `SIN_APU`; ningún `SIN_CONCEPTOS`; 8,639 en total; `filas_leidas == 4281`, `filas_validas == 0`, `filas_rechazadas == 4281` y `len(preparacion["conceptos"]) == 0`. Que una celda rota no se importa como cero lo prueba TC-19/TC-25 con un libro que sí deja conceptos válidos | **rechazo** | `CA-3` | `archivos_reales` · A7 |
| TC-41 | `test_hdu001_esc09_eniti_sin_duplicados` (real): cero `DUPLICADO` del catálogo; los seis `DUPLICADO` llevan el sufijo `(causa: CODIGO_EN_VARIAS_HOJAS)` | **rechazo** del rechazo | `CA-8` | `archivos_reales` · A7 |
| TC-42 | `test_tkt015_eniti_48_errores` (real): `CON_ERRORES` con 48 errores (20 `UNIDAD_DESCONOCIDA` de `CARGO_DESCONOCIDO`, 5 `REF_ROTA` de `ERROR_DE_FORMULA`, 6 `DUPLICADO` de `CODIGO_EN_VARIAS_HOJAS`, 1 `REF_ROTA` de `ANALISIS_SIN_CODIGO` y 16 `SIN_APU`) persistidos; un solo análisis en la preparación; los conceptos de `620014`, `620045` y `620050` sí están en ella | **rechazo** | `CA-10` | `archivos_reales` · A7 |
| TC-INV-1 | Las suites de TKT-013 y TKT-014 sin cambios, con y sin las variables: 4,281 y 5,028 conceptos | regresión | `CA-R1` | A7 |
| TC-INV-2 | `verificar_float`, `lint-imports`, `ruff` y `mypy` en verde; los módulos nuevos de `dominio/` solo importan la biblioteca estándar y `tipos_base` | regresión | `CA-R2` | A9 y B7 |

### TKT-015b · barrido

| # | Caso | Tipo | Criterio | Archivo · fila |
|---|---|---|---|---|
| TC-43 | `test_tkt015_dos_barridos_simultaneos_procesan_cada_id_una_vez`: una definición sobre `importacion` con un **gancho de prueba** que anota los ids; dos hilos con `Barrier(2)` y dos sesiones ejecutan `barrer` sobre una `ANALIZANDO` vencida → uno devuelve el id y el otro una tupla vacía, y el gancho recibió el id **una sola vez**; un tercer barrido no devuelve nada; un `55P03` es fallo | **concurrencia** | `CA-16` esc. 2 | `barrido` · B1 |
| TC-44 | `test_tkt015_barrido_reutilizable_con_otra_definicion`: con el rol de migración, la prueba crea `prueba_dos_pasos (id uuid PRIMARY KEY, estado text NOT NULL, creado_en timestamptz)` y la borra al final; una definición con `PENDIENTE`, `CADUCADO` y `creado_en` → con el rol de aplicación, la vencida pasa a `CADUCADO`, la vigente no, y el gancho recibe solo la vencida | feliz | `CA-17` | `barrido` · B1 |
| TC-45 | `test_tkt015_trabajos_solo_importa_stdlib_y_sqlalchemy`: recorre con `ast` los `.py` de `trabajos/`; cada importación es de `sys.stdlib_module_names` o de `sqlalchemy`; ninguna de `cimenta`, `servidor`, `fastapi` ni `structlog` | **rechazo** | `CA-17`, `CA-R2` | `barrido` · B1 |
| TC-43b | `test_hdu001_esc29_dos_barridos_un_solo_proceso_interrumpido`: lo mismo que TC-43 con el gancho real de `definicion_barrido_importacion` → un único `PROCESO_INTERRUMPIDO` | **concurrencia** | `CA-16` esc. 2 | `barrido_importacion` · B2 |
| TC-46 | `test_hdu001_esc29_barrido_marca_la_interrumpida`: `ANALIZANDO` con `latido = now() - 2 × umbral` → `CON_ERRORES` con un único `PROCESO_INTERRUMPIDO` de ubicación nula y el mensaje de `REINICIO`; la obra no tiene ninguna `ANALIZANDO`; `iniciar_analisis` la acepta | **rechazo** | `CA-15` | `barrido_importacion` · B2 |
| TC-47 | `test_hdu001_esc29_barrido_latido_nulo_es_vencido`: `ANALIZANDO` con latido nulo → barrida con su `PROCESO_INTERRUMPIDO` | borde | `CA-16` · `PA-15.5` | `barrido_importacion` · B2 |
| TC-48 | `test_hdu001_esc29_barrido_no_toca_lo_vivo`: una `ANALIZANDO` con latido de hace un segundo, una `VALIDADO` y una `CON_ERRORES` con latido viejo → ninguna cambia de estado ni gana errores | **rechazo** | `CA-16` esc. 1 | `barrido_importacion` · B2 |
| TC-49 | `test_tkt015_definicion_barrido_importacion`: `definicion_barrido_importacion(timedelta(seconds=60))` tiene `tabla="importacion"`, `estado_intermedio="ANALIZANDO"`, `estado_vencido="CON_ERRORES"`, `columna_marca="latido"` y el umbral recibido, y se importa desde `cimenta.presupuesto.interfaz` (está en su `__all__`) | feliz | `CA-17` | `barrido_importacion` · B2 |

### TKT-015b · avance

| # | Caso | Tipo | Criterio | Archivo · fila |
|---|---|---|---|---|
| TC-50 | `test_tkt015_lector_con_avance_no_cambia_el_resultado`: con el libro de cuatro hojas, `leer_libro_presupuesto` con y sin `al_avanzar` da resultados iguales y las llamadas son, en orden, `(1, 4)`, `(2, 4)`, `(3, 4)` y `(4, 4)`; con `posicion_catalogo=2`, las mismas; con un libro sin hoja de catálogo y tres hojas de APU, `(1, 3)`, `(2, 3)` y `(3, 3)`; con `b""`, ninguna llamada | regresión | `CA-R1`, `CA-13` | `avance` · B3 |
| TC-51 | `test_hdu001_esc04_progreso_de_lectura`: `(0, 5)` → `0`; `(5, 5)` → `0.9`; `(1, 3)` → `0.300000`; `(4, 7)` → `0.514285` (con `ROUND_HALF_UP` sería `0.514286`); `(7, 5)` → `0.9`; `(1, 0)` → `0` | borde | `CA-13` | `avance` · B3 |
| TC-INV-3 | Las suites de TKT-013 y TKT-014 tras B3, con la prueba de firma de TKT-014 actualizada | regresión | `CA-R1` | B3 |

### TKT-015b · ejecutor

Cada prueba crea un `EjecutorAnalisis` con `intervalo_latido=timedelta(milliseconds=200)`, el origen en memoria y `trabajo_de_prueba` (o el trabajo real donde se dice), y lo cierra en un `finally`.

| # | Caso | Tipo | Criterio | Archivo · fila |
|---|---|---|---|---|
| TC-52 | `test_tkt015_analisis_en_otro_proceso`: con `bloquear:<ruta>`, `solicitar_analisis` vuelve con la importación todavía `ANALIZANDO`; al `liberar`, la preparación guarda un `pid` distinto de `os.getpid()` | feliz | `CA-12` | `ejecutor` · B4 |
| TC-53 | `test_tkt015_dos_importaciones_en_serie`: dos solicitudes seguidas con `anotar` → los intervalos `[inicio, fin]` no se solapan y los dos `pid` son iguales | **concurrencia** | `CA-12` | `ejecutor` · B4 |
| TC-54 | `test_hdu001_esc04_progreso_y_latido_mientras_analiza`: con `avance:<ruta>`, entre dos consultas separadas por `esperar_latidos(1, 30)`, el estado es `ANALIZANDO`, `0 < progreso1 <= progreso2 < 1` y `latido2 > latido1`; al liberar, `progreso == 1` y el estado no es `ANALIZANDO` | feliz | `CA-13` | `ejecutor` · B4 |
| TC-55 | `test_tkt015_el_progreso_nunca_baja`: con `avance-desordenado:<ruta>`, tras `esperar_latidos(2, 30)`, `progreso` es el de `(3, 5)` | **rechazo** | `CA-13` | `ejecutor` · B4 |
| TC-56 | `test_tkt015_resumir_avances_guarda_el_mayor`: `resumir_avances([(a, 1, 5), (a, 3, 5), (b, 2, 4), (a, 2, 5)])` → `{a: (3, 5), b: (2, 4)}` | borde | `CA-13` | `ejecutor` · B4 |
| TC-57 | `test_tkt015_la_que_espera_turno_no_vence`: la primera con `bloquear:<ruta>` y la segunda en cola; tras `esperar_latidos(3, 30)`, el latido de la segunda avanzó, y `barrer` con un umbral de un segundo no la toca | **rechazo** | `CA-13`, `CA-16` · `PA-15.4` | `ejecutor` · B4 |
| TC-58 | `test_hdu001_esc29_excepcion_del_trabajo`: `fallar` → `CON_ERRORES` con el mensaje de `EXCEPCION` y `preparacion IS NULL`; `structlog.testing.capture_logs` trae `analisis_interrumpido` con `importacion_id` y `motivo`; una segunda con `anotar` termina `VALIDADO` | **rechazo** | `CA-14`, `CA-11` esc. 2 | `ejecutor` · B4 |
| TC-59 | `test_hdu001_esc29_trabajador_muerto`: se encolan **las dos antes de liberar**: la primera con `morir:<ruta>` y la segunda con `anotar`; al liberar, la primera queda `CON_ERRORES` con el mensaje de `TRABAJADOR_TERMINADO` y `preparacion IS NULL`, y la segunda termina `VALIDADO` con un `pid` distinto del de la primera | **rechazo** | `CA-14`, `CA-11` esc. 2 | `ejecutor` · B4 |
| TC-60 | `test_hdu001_esc29_archivo_ilegible`: `leer_contenido` lanza → `CON_ERRORES` con el mensaje de `ARCHIVO_ILEGIBLE`, sin enviar nada al trabajador | **rechazo** | `CA-14` | `ejecutor` · B4 |
| TC-61 | `test_hdu001_esc29_reintento_por_solicitar_analisis`: tras un `PROCESO_INTERRUMPIDO`, `solicitar_analisis` con el trabajo real y un libro sintético válido la encola de nuevo y termina `VALIDADO`, sin el error anterior | feliz | `CA-18` esc. 2 | `ejecutor` · B4 |
| TC-62 | `test_hdu001_esc29_ejecutor_cerrado_deja_reinicio`: con el ejecutor cerrado, `solicitar_analisis` lanza `EjecutorCerrado` y la importación queda `CON_ERRORES` con el mensaje de `REINICIO` | **rechazo** | `CA-12`, `CA-14` | `ejecutor` · B4 |

### TKT-015b · arranque

| # | Caso | Tipo | Criterio | Archivo · fila |
|---|---|---|---|---|
| TC-63 | `test_hdu001_esc29_el_arranque_barre_antes_de_servir`: con una `ANALIZANDO` vencida y `motor=motor_aplicacion`, dentro de `with TestClient(...)` la importación ya está `CON_ERRORES` con su `PROCESO_INTERRUMPIDO` y `app.state.ejecutor_analisis` existe; al salir, `encolar` lanza `EjecutorCerrado` | **rechazo** | `CA-15` | `arranque` · B5 |
| TC-64 | `test_tkt015_ajustes_de_trabajos`: sin variables, `5` y `60`; umbral `10` con intervalo `5` → `ConfiguracionInvalida` que nombra `CIMENTA_TRABAJOS_UMBRAL_VENCIMIENTO` y no su valor; intervalo `0` → la nombra; intervalo `0` y umbral `10` a la vez → solo `CIMENTA_TRABAJOS_INTERVALO_LATIDO`, sin `KeyError` | **rechazo** | `CA-15` · `PA-15.4` | `arranque` · B5 |
| TC-65 | `test_tkt015_sin_variables_de_base_el_servidor_arranca`: `monkeypatch.setattr(servidor.fabrica, "crear_motor_aplicacion", doble)`, con un doble que lanza `AssertionError` si se llama (`fabrica.py` lo importa de `herramientas.conexion` y lo usa por ese nombre); `entorno` = `ENTORNO_DE_PRUEBA` sin `CIMENTA_DB_HOST`, `CIMENTA_DB_PUERTO` ni `CIMENTA_DB_NOMBRE`, sin `motor` → `with TestClient(...)` arranca, `/openapi.json` responde `200`, `app.state.ejecutor_analisis is None`, `capture_logs` trae `trabajos_omitidos` con `motivo="sin variables de base"` y el doble no se llamó | regresión de invariante | TKT-006 CA-R4 y D-2 · P16 | `arranque` · B5 |
| TC-66 | `test_tkt015_con_base_y_barrido_fallido_no_arranca`: con un `motor` cuyo `connect` lanza, entrar en `with TestClient(...)` propaga la excepción del barrido | **rechazo** | P11 · `CA-15` | `arranque` · B5 |
| TC-67 | `test_tkt015_variables_de_base_presentes`: las tres en el mapa → `True`; cualquiera ausente o vacía → `False` | borde | P16 | `arranque` · B5 |

### Matriz criterio → TC → fila → entrega

| Criterio | TC | Filas | Entrega |
|---|---|---|---|
| `CA-1` | TC-01, TC-04, TC-19, TC-24 | A1, A5, A6 | a |
| `CA-2` | TC-06, TC-20, TC-25 | A2a, A5, A6 | a |
| `CA-3` | TC-38, TC-40 | A6, A7 | a |
| `CA-4` | TC-01, TC-10, TC-26 | A1, A2b, A6 | a |
| `CA-5` | TC-07, TC-27 | A2a, A6 | a |
| `CA-6` (esc. 28) | TC-08, TC-28 | A2a, A6 | a |
| `CA-7` | TC-11, TC-15, TC-29 | A2b, A6 | a |
| `CA-8` | TC-12, TC-41 | A2b, A7 | a |
| `CA-9` (esc. 27) | TC-09, TC-30 | A2a, A6 | a |
| `CA-10` | TC-05, TC-13, TC-39, TC-42 | A2a, A2b, A6, A7 | a |
| `CA-11` | TC-14, TC-16, TC-17, TC-21, TC-22, TC-31, TC-32, TC-38 · TC-58, TC-59 | A2b, A3, A4, A5, A6 · B4 | a y b |
| `CA-12` | TC-23 · TC-52, TC-53, TC-62 | A5 · B4 | a y b |
| `CA-13` | TC-50, TC-51, TC-54, TC-55, TC-56, TC-57 | B3, B4 | b |
| `CA-14` (esc. 29) | TC-03 · TC-58, TC-59, TC-60, TC-62 | A1 · B4 | a y b |
| `CA-15` (esc. 29) | TC-03, TC-34 · TC-46, TC-63, TC-64 | A1, A6 · B2, B5 | a y b |
| `CA-16` (esc. 29) | TC-37 · TC-43, TC-43b, TC-47, TC-48, TC-57 | A6 · B1, B2, B4 | a y b |
| `CA-17` | TC-44, TC-45, TC-49 | B1, B2 | b |
| `CA-18` | TC-02, TC-33, TC-34, TC-35, TC-36 · TC-61, TC-62 | A1, A6 · B4 | a y b |
| `CA-S1` | TC-14, TC-16, TC-20, TC-25 | A2b, A3, A5, A6 | a |
| `CA-R1` | TC-INV-1 · TC-50, TC-INV-3 | A7 · B3 | a y b |
| `CA-R2` | TC-INV-2 · TC-45, suites de fronteras | A9 · B1, B7 | a y b |
| `CA-R3` | TC-18 | A4 | a |
| P16 (invariante de TKT-006) | TC-65, TC-66, TC-67 | B5 | b |

**Conteos:** 68 casos numerados (TC-01 a TC-67, sin huecos, más TC-43b): 42 en a (TC-01 a TC-42) y 26 en b (TC-43 a TC-67 y TC-43b); más TC-INV-1 a TC-INV-3. 23 mutantes: 12 en a (M-01 a M-12) y 11 en b (M-13 a M-23). 21 filas: 12 en a (A-pre, A0, A1, A2a, A2b, A3 a A9) y 9 en b (B0, B1, B1b, B2 a B7). **Concurrencia** (varios actores a la vez, sea cual sea su tipo en la tabla): TC-35, TC-43, TC-43b, TC-53 y TC-57. **El reinicio** se simula con el barrido sobre un latido viejo (TC-46, TC-63), como dice la DoD.

### Mutación

Cada mutante se aplica a mano, se ejecuta la prueba indicada, se ve en rojo y se revierte. Lo que se mutó y qué cayó se pega en `impl.md`.

| # | Mutante | Test que debe ponerse rojo | Fila |
|---|---|---|---|
| M-01 | `ERROR_DE_FORMULA` mapeado a `SIN_CONCEPTOS` | TC-06, TC-25 | A9 |
| M-02 | Se borra una fila de `TIPO_POR_CAUSA` | TC-05 | A9 |
| M-03 | `es_celda_de_rendimiento` sin la comprobación de columna | TC-08 (unidad vacía en `D`) | A9 |
| M-04 | `detectar_duplicados` compara la descripción sin normalizar | TC-12 | A9 |
| M-05 | `detectar_duplicados` marca todo código repetido | TC-12, TC-41 | A9 |
| M-06 | `estado_tras_analisis` con `len(errores) > 1` | TC-01, TC-26 | A9 |
| M-07 | `puede_analizarse` admite `CON_ERRORES` con cualquier error | TC-02, TC-33 | A9 |
| M-08 | `iniciar_analisis` sin `FOR UPDATE` | TC-35 | A9 |
| M-09 | `cerrar_analisis` sin `AND estado = 'ANALIZANDO'` | TC-37 | A9 |
| M-10 | `CONCEPTO_SIN_PARTIDA` vuelve a `SIN_CONCEPTOS` | TC-05, TC-40 | A9 |
| M-11 | Los `DUPLICADO` de hoja de APU también rechazan filas del catálogo | TC-14, TC-42 | A9 |
| M-12 | `registrar_interrupcion` escribe la preparación | TC-32 | A9 |
| M-13 | El barrido sin `IS NULL` en la marca | TC-47 | B7 |
| M-14 | El barrido sin la condición de estado intermedio | TC-48 | B7 |
| M-15 | `<` por `>` en la comparación con el umbral | TC-46, TC-48 | B7 |
| M-16 | El despachador refresca solo la importación en curso | TC-57 | B7 |
| M-17 | El despachador envía al grupo varias importaciones en vez de una a la vez | TC-59 (la segunda cae también con `BrokenProcessPool`) | B7 |
| M-18 | `registrar_progreso` sin `GREATEST` | TC-55 | B7 |
| M-19 | `resumir_avances` guarda el primer avance en vez del mayor | TC-56 | B7 |
| M-20 | `progreso_de_lectura` con `ROUND_HALF_UP` | TC-51 (`(4, 7)`) | B7 |
| M-21 | `al_avanzar` se llama también para la hoja del catálogo dentro del bucle | TC-50 | B7 |
| M-22 | El `lifespan` barre siempre, sin mirar si la base está configurada | TC-65 y `tests/test_servidor_arranque.py` | B7 |
| M-23 | El `lifespan` traga la excepción del barrido con base configurada | TC-66 | B7 |

## Impacto

Análisis del arquitecto, revisado por `revisor-impacto` (veredicto: sin frontera cruzada) y por dos revisiones independientes de coherencia y de fidelidad al código.

| Qué se toca | Quién depende | Riesgo | Mitigación |
|---|---|---|---|
| Columna `importacion.preparacion` y su `CHECK` (a) | TKT-017 y TKT-018 | Un formato que no les baste | `formato: 1`; conserva todo lo leído y no cuantiza |
| `DatosPresupuesto.importacion` de `conftest.py` | Pruebas de TKT-011 | El `CHECK` rechaza una fila con preparación en `ANALIZANDO` | La fábrica no escribe `preparacion`; TC-INV-1 corre la suite |
| `leer_libro_presupuesto` gana `al_avanzar` (b) | TKT-014: la prueba de firma (`tests/test_tkt014_lector.py:143-146`) se pone roja; la de una sola apertura no debe cambiar | Cambiar el resultado o las aperturas | Solo por nombre con `None`; B3 actualiza la prueba de firma conservando `:148-158`; TC-50 |
| `crear_aplicacion` con `lifespan` (b) | La fixture `cliente` (`with TestClient`) y las tres pruebas de `tests/test_servidor_arranque.py` que arrancan sin variables de base | Un barrido obligatorio rompería el arranque sin base | P16 (a); ejecutor perezoso; B5 corre `tests/test_servidor_arranque.py` completo; TC-65 y M-22 |
| `AjustesServidor` con dos campos (b) | `tests/test_tkt057_arranque.py:112-113` | La prueba se pone roja | B5 la actualiza; TC-64 |
| Paquete `trabajos/` y `backend/pyproject.toml` (b) | `lint-imports`, mypy, el trabajo `fronteras`; TKT-059; las tres suites de fronteras | `Could not find package trabajos` y cuatro aserciones `(15, 0)` en rojo | B1 las actualiza; E-7 antes |
| `herramientas/conexion.py` gana `variables_de_base_presentes` (b) | `contrasenas_roles`, `semilla_local`, migraciones | Ninguno: función nueva | TC-67 |
| Cobertura en CI (b) | `ci.yml` mide `--cov=cimenta --cov=tipos_base --cov=contrato_error --cov=servidor`; `tools/tests/test_definicion_ci.py` | `trabajos/` sin medir; el hijo `spawn` tampoco | B1b añade `--cov=trabajos` y un caso nuevo que lee el `ci.yml` real. El hijo no se mide: limitación declarada en la DoD |
| Tiempos del rol de aplicación | `cerrar_analisis`, `insertar_errores`, TC-35, TC-43 y TC-43b | Una sentencia de más de 15 s, o un `55P03` en concurrencia | E-4; condición de parada en 5 s; las pruebas tratan un `55P03` como fallo |
| `CausaHallazgo` | Una causa futura | Que llegue sin destino | TC-05 |
| `ESTADO_NO_PERMITE_OPERACION` y `detalle` | TKT-018 | Que necesite otro código o acciones (`PA-15.7`) | Escritos aquí; TKT-018 añade las acciones |
| `app.state.ejecutor_analisis` puede ser `None` (b) | TKT-018 | Una ruta que no lo compruebe | Declarado en el diseño; TKT-018 lo trata en su dependencia |

**Fronteras entre módulos:** No. Todo el código nuevo de negocio vive en `presupuesto`, y `dominio/` solo importa la biblioteca estándar y `tipos_base`. `trabajos/` está fuera de `cimenta/`, no importa ningún módulo y lo vigila un contrato nuevo de lista blanca. `servidor/`, raíz de composición, importa `cimenta.presupuesto.interfaz` y `trabajos.barrido`; ningún módulo importa `servidor/`. Los contratos existentes no cambian.

## Documentación afectada

| Documento | Qué cambia | Ticket |
|---|---|---|
| `docs/04-historias-usuario.md` y efectos colaterales | Escenarios 28 y 29 (fila A-pre): DoD de HDU-001 de 27 a 29; total de `:62` de 162 a 164; `docs/06-stack-tecnologico.md:189` y `:397`; la fila «Escenarios de aceptación \| 162» de `README.md`; los `x-escenarios` del borrador OpenAPI; `tools/historias_activas.txt` si procede | a (A-pre) |
| `docs/03-modelo-datos.md` §11 | La columna `preparacion jsonb` en el diagrama (`:1020-1028`) y un párrafo: qué guarda, el formato 1, el `CHECK` y por qué no es tabla (a). En el diagrama cambian los rótulos de `progreso` y `latido`; `:1044` («nulo fuera de `ANALIZANDO`») pasa a «nulo antes del primer análisis; 1 al terminar; se conserva tras una interrupción» (P7); `:1050` pasa a «el parseo corre en un proceso aparte y el latido lo refresca el proceso del API mientras el trabajo está en cola o en curso» (b) | a y b |
| `docs/05-tickets-trabajo.md`, ficha de TKT-015 | Subsección «Partición en dos tickets hermanos»; «Las filas válidas se conservan en preparación» pasa a «El resultado válido se guarda en `importacion.preparacion`» (a). `:691` («El trabajo refresca `importacion.latido`») pasa a «El proceso del API refresca `importacion.latido` del trabajo en curso y de los que esperan turno, y el trabajo informa el progreso» (P8, b) | a y b |
| `docs/05-tickets-trabajo.md`, fichas de TKT-017 y TKT-059 | TKT-017 (`:724`): «Depende de TKT-015» pasa a «Depende de TKT-015b». TKT-059: depende de TKT-015b y reutiliza `trabajos.barrido.DefinicionBarrido` con `columna_marca="creado_en"`. TKT-016 (`:705`) no cambia: depende solo de TKT-014b | b |
| `sdd/tickets/tkt-015/spec.md` | Lo ajusta el orquestador: los criterios de la partición; `PA-15.2` y `PA-15.12` resueltas | a |
| `docs/adr/` y `docs/adr/README.md` | ADR-036 (a) y ADR-037 (b), con su fila en el índice | a y b |
| `CLAUDE.md` (`:14`), `README.md` (`:30` y `:264`), `llms.txt` (`:27`) | El conteo de ADR pasa a 36 en a y a 37 en b. `README.md:264` dice hoy 34 (ya desfasado): se corrige en a | a y b |
| `CLAUDE.md`, «Estructura del backend» | `trabajos/` en la lista de paquetes fuera de `cimenta/`, y «`import-linter` analiza `cimenta/`, `tipos_base/` y `trabajos/`» (P5) | b |
| `docs/convenciones.md` (`:64`) | `trabajos/` en la lista de paquetes fuera de `cimenta/` | b |
| `docs/02-arquitectura.md` §9 | El parseo en un proceso aparte que gobierna un hilo despachador del API; el latido lo refresca el API; el barrido es el de `trabajos/` y corre en el `lifespan` antes de servir, si hay base configurada. `CON_ERRORES → ANALIZANDO` se rotula «se reintenta tras una interrupción» (`PA-15.7`) | b |
| `docs/02-arquitectura.md` (`:147`), §7.7 (`:412`) y §12 (`:645`) | «dentro del propio proceso del API» pasa a «el proceso del API la gobierna y la parsea en un proceso hijo de un solo trabajador»; «con el mismo mecanismo» enlaza ADR-037; ADR-036 y ADR-037 en la tabla de decisiones | a y b |
| `docs/06-stack-tecnologico.md` §3.3 (`:124`, `:132`) y `:366` | «FastAPI ejecuta la tarea en segundo plano» pasa a «un hilo despachador del proceso del API la envía a un `ProcessPoolExecutor` de un trabajador»; «El trabajo actualiza `importacion.latido`» pasa a «el proceso del API refresca `importacion.latido`»; la fila de `RNF-17` cita TC-46 y TC-63 | b |
| `docs/api/openapi.yaml` (`:4681`) | **Ajuste opcional:** `progreso` («Fracción leída mientras está `ANALIZANDO`») pasa a la redacción de `docs/03` | b, opcional |
| `.env.example` y `docs/arranque-local.md` | `CIMENTA_TRABAJOS_INTERVALO_LATIDO` y `CIMENTA_TRABAJOS_UMBRAL_VENCIMIENTO`, **comentadas** con su valor por omisión, como los ajustes opcionales de TKT-057 (`tests/test_tkt057_entorno.py:64-85`); que sin variables de base no hay barrido, y que con ellas `fastapi dev` y `fastapi run` exigen la base arriba y migrada (`:52-55`). `:41` suma `trabajos` a lo que analiza `lint-imports` y `:124` suma `--cov=trabajos` | b |
| `llms.txt` (`:19`), `docs/04-historias-usuario.md` (`:469-470`) y `docs/07-especificacion-api.md` (`:277-279`) | `:19` de 162 a 164 escenarios; «Los 27 son de fase 1» pasa a 29; las tres filas de la tabla de `x-escenarios` suman los escenarios 28 y 29 (efectos de A-pre) | a (A-pre) |
| `CLAUDE.md`, regla 11, y consecuencias de ADR-013 | Una frase: la única excepción a «nunca `async def`» es el `lifespan`, que solo delega a `run_in_threadpool` (P13), para que la regla no quede contradicha | b |
| `sdd/tickets/tkt-015/_index.md` y `sdd/_evolucion.md` | Lo ajusta el orquestador | a y b |

El borrador OpenAPI no cambia en su contrato: no hay rutas, y `ESTADO_NO_PERMITE_OPERACION` ya está en `CodigoConflicto`. Solo cambian los `x-escenarios` (A-pre) y, si se quiere, la descripción de `progreso`.

### Definition of Done: lo que este diseño añade

- En TKT-015b, `--cov=trabajos` en el pipeline (B1b). **Limitación declarada:** el código que solo corre en el hijo `spawn` (`ejecutar_en_trabajador`, `notificar_avance`, `_iniciar_trabajador`, unas diez líneas) no lo mide `pytest-cov`; lo ejercitan TC-52 a TC-62. «La cobertura del módulo `presupuesto` no baja» se lee sobre lo que se mide en el proceso de la prueba; `analizar_contenido` sí se mide, porque TC-19 a TC-23 la ejecutan en él.
- `tests/test_servidor_arranque.py` completo en verde en B5.
- Las pruebas existentes que cambian (fronteras, firma de TKT-014, `test_tkt057_arranque.py`) las cambia el tester, y `impl.md` deja el antes y el después.
- `python tools/verificar_escenarios.py` sin escenarios huérfanos de HDU-001 al cerrar a (los 28 y 29 cubiertos).

## ¿Merece ADR?

Sí, dos, en formato MADR:

- **ADR-036** (fila A8) · `docs/adr/<fecha>-preparacion-de-importacion-en-jsonb.md`. Opciones: columna `jsonb` (elegida), tabla 1:1, tablas normalizadas, `bytea` con `pickle`. Consecuencias: las consultas nombran columnas; el formato lleva versión; el dinero viaja como cadena sin cuantizar y `None` como `null`; el `CHECK` hace imposible la preparación a medias en el reintento; una preparación de un libro real puede quedar casi vacía (ENITI conserva un solo análisis de 24; Union, ningún concepto). Incluye el mapa de causas a tipos (`PA-15.2`), la regla de qué rechaza cada `DUPLICADO` y por qué no se amplía el `CHECK`.
- **ADR-037** (fila B6; cita ADR-022, que descartó añadir a `root_packages` con contratos propios y dejó la puerta abierta, y anota la excepción del `lifespan` `async def` a la regla 11 y a ADR-013) · `docs/adr/<fecha>-trabajos-en-dos-pasos-y-barrido-de-arranque.md`. Opciones de latido: el hijo con su conexión, el padre (elegida). Opciones de cola: varias en el grupo, una a la vez (elegida). Opciones de ubicación: `servidor/`, un módulo en `cimenta/` (rompe `esqueleto-modulos`), `tipos_base/` (exige solo biblioteca estándar), paquete propio (elegida), que sigue el patrón de `tipos_base/` —paquete raíz con contrato de lista blanca, `permitidos = ["sqlalchemy"]`— y no el de `contrato_error/`; por qué lista blanca y no `forbidden`. Opciones de arranque (P16): barrer siempre, omitir sin base configurada con aviso (elegida), mover las pruebas a un entorno con base. Consecuencias: un trabajo colgado mantiene su latido mientras viva el API (P12); el cierre deja las importaciones para el barrido siguiente; el `lifespan` es la única corrutina del backend; sin variables de base no hay barrido ni ejecutor; el hijo no se mide en cobertura; el progreso se redondea con `ROUND_DOWN` fuera de `cuantizar()` `(asumido)`.

## Pasada adversarial

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Crítica | Si el latido lo escribe el API, un trabajo que se cuelga en el hijo late para siempre: la obra queda bloqueada hasta reiniciar | Consecuencia declarada en ADR-037; remedio en P12, con la recomendación de un ticket propio. Reiniciar lo resuelve |
| 2 | Alta | Con varios trabajos en el grupo, la muerte del trabajador hace fallar a los que esperaban | El despachador envía uno a la vez; TC-59 encola las dos antes de liberar, y M-17 la pone roja |
| 3 | Alta | `ANALISIS_SIN_CODIGO` en `SIN_APU` daría 51 `SIN_APU` en Union | Va a `REF_ROTA`; TC-40 cuenta 31 |
| 4 | Alta | `CA-R1` prohíbe inferir hallazgos, y `RENDIMIENTO_AUSENTE` se decide por la columna | Es el `VALOR_AUSENTE` que el lector ya marcó, clasificado por su celda. TC-08 fija la letra contra el lector real. P2 |
| 5 | Alta | El `lifespan` es `async`, y la regla 11 dice «nunca `async def`» | El cuerpo solo delega con `run_in_threadpool`. P13 |
| 6 | Media | Un resultado que llega tras el barrido de otra instancia resucitaría la importación | `cerrar_analisis` e `interrumpir` filtran por `ANALIZANDO`; TC-37 y M-09 |
| 7 | Media | Unos 8,600 errores alargan la transacción | Lote en una transacción; E-4 mide cada sentencia; TC-38 prueba el todo o nada |
| 8 | Media | Cada prueba de identidad levanta la aplicación: un ejecutor con procesos la haría lenta | Ejecutor perezoso; B5 corre esas suites |
| 9 | Media | Un `SIN_APU` en la primera fila deja «válidas» las demás filas del código | Rechaza todas las filas del código: P3 |
| 10 | Baja | `CARGO_DESCONOCIDO` como `UNIDAD_DESCONOCIDA` puede confundir | El mensaje nombra el cargo y el catálogo; alternativa en P2 |
| 11 | Alta | (Orquestador, `abogado-del-diablo`.) Mandar `CONCEPTO_SIN_PARTIDA`, `PROFUNDIDAD_EXCEDIDA` y `CODIGO_SIN_CONCEPTO` a `SIN_CONCEPTOS` contradice la decisión de la persona dueña del 2026-11-03 y el borrador OpenAPI, y Union mostraría cinco «la hoja no trae ninguna fila de concepto» en un catálogo de 4,281 conceptos | Aplicado en el mapa; la persona dueña lo confirma en P2 |
| 12 | Media | (Orquestador.) La razón para no partir en tres es débil: las cifras de `CA-3` y `CA-10` salen de `analizar_contenido`, que no toca la base, y la entrega a duplica el precedente de TKT-014 | Queda en P1, con las tres entregas como alternativa; la recomendación se mantiene en dos |
| 13 | Alta | (Revisión de fidelidad.) Si los `DUPLICADO` de hoja de APU rechazaran filas del catálogo, ENITI perdería conceptos válidos | La regla los limita a su análisis; TC-14, TC-42 y M-11 |
| 14 | Alta | (Revisión de impacto.) Un barrido obligatorio rompe el arranque sin variables de base, invariante de TKT-006 | P16 (a); TC-65 a TC-67; M-22 y M-23 |
| 15 | Media | (Revisión de coherencia.) Un archivo de pruebas compartido por varias filas con un import de un módulo que no existe tumba la recolección de los tests ya verdes | Regla de importación dentro del test y un archivo por fila |

## Riesgos

| Riesgo | Probabilidad | Impacto | Qué se hace |
|---|---|---|---|
| A0 no reproduce E-1 | Muy baja | Medio: cambian `CA-3` y `CA-10` | `/sdd-escalar` antes de A1 |
| E-5 falla en Linux | Baja | Alto: no hay progreso mientras corre | `/sdd-escalar` antes de B4 con la alternativa de un `Manager().Queue()` |
| E-7 muestra que la lista blanca no admite un paquete raíz como origen | Baja | Medio | `/sdd-escalar` antes de B1 con la alternativa `forbidden` |
| La preparación de ENITI pasa de 20 MB comprimida | Muy baja | Medio | `/sdd-escalar` en A6 con la alternativa de tabla 1:1 |
| Una sentencia del cierre pasa del `statement_timeout`, o un `55P03` en TC-35, TC-43 o TC-43b | Baja | Alto | E-4; condición de parada en 5 s; no se cambian los tiempos del rol sin la persona dueña (A5, A6, B1) |
| Pruebas del ejecutor intermitentes | Media | Medio | Sincronización con `esperar_latidos` y `esperar_inactivo`, sin `sleep`; tres pasadas seguidas en B4 |
| Un trabajo colgado bloquea la obra hasta reiniciar | Baja | Alto | P12; ADR-037 |
| Arrancar sin variables de base deja de funcionar | Baja con P16 | Alto | P16 (a); TC-65; B5 corre `tests/test_servidor_arranque.py` completo |
| El código del hijo no se mide en cobertura | Cierta | Bajo | Limitación en la DoD |
| El tamaño de cada PR (~1,790 y ~1,380) sigue por encima del tope | Cierta | Medio | Precedente de TKT-013 y TKT-014; P1 ofrece partir en tres |

## Preguntas para el gate

| # | Pregunta | Recomendación |
|---|---|---|
| P1 | ¿Se parte en TKT-015a y TKT-015b, con un PR cada uno y fusión a → b? | Sí. Si los ~1,790 de a pesan demasiado, tres entregas (dominio puro · persistencia y reales · trabajo y barrido), a costa de un PR más |
| P2 | ¿Se aprueba el mapa de las 22 causas, con la corrección aplicada (`CONCEPTO_SIN_PARTIDA`, `PROFUNDIDAD_EXCEDIDA` y `CODIGO_SIN_CONCEPTO` → `REF_ROTA`; `SIN_CONCEPTOS` solo para las cinco causas de hoja)? Las demás dudosas: `CARGO_DESCONOCIDO` → `UNIDAD_DESCONOCIDA` (alternativa `REF_ROTA`); `ANALISIS_SIN_CODIGO` → `REF_ROTA`; `TIPO_EN_CONFLICTO` → `DUPLICADO`; y que solo `VALOR_AUSENTE` en la celda de rendimiento sea `RENDIMIENTO_AUSENTE` | Sí, tal como está en el mapa: cada tipo agrupa por lo que el Director de Proyectos tiene que corregir, y el mensaje lleva siempre la causa cruda |
| P3 | Un `SIN_APU` o un `DUPLICADO` del catálogo ¿rechazan **todas** las filas del código, y los `DUPLICADO` de hoja de APU y los errores de un análisis rechazan solo ese análisis? | Sí: todas las filas del código tienen el mismo defecto, y un concepto válido no se pierde por un defecto de su análisis |
| P4 | ¿La preparación va en `importacion.preparacion jsonb` (migración `0009` con su `CHECK`) y se escribe ADR-036? | Sí |
| P5 | ¿Se crea `trabajos/` fuera de `cimenta/`, se añade a `root_packages` con su lista blanca, y se actualiza «Estructura del backend» de `CLAUDE.md`? | Sí: `esqueleto-modulos` impide un undécimo módulo, y `archivos` no puede importar `presupuesto` |
| P6 | El mapa de insumos existentes ¿toma **todos** los insumos, activos o no, ordenados por `codigo`, y gana el primero si dos descripciones normalizan igual? | Sí; TKT-017 decide qué hacer con un inactivo |
| P7 | `progreso` queda en 1 al terminar y se conserva tras una interrupción. ¿Se corrige `docs/03` (y, si se quiere, la descripción del OpenAPI)? | Sí: la spec aprobada manda |
| P8 | ¿El latido lo escribe el proceso del API, para el trabajo en curso y los que esperan? | Sí: dice lo que el barrido necesita saber y resuelve `PA-15.4` |
| P9 | ¿Intervalo de 5 s y umbral de 60 s, configurables, con el umbral al menos tres veces el intervalo? | Sí |
| P10 | ¿Los cuatro mensajes de `PROCESO_INTERRUMPIDO`, con la clase de la excepción solo en el registro? | Sí |
| P11 | **Con la base configurada** (P16), si el barrido falla en el arranque, ¿la aplicación no arranca? | Sí: con base inalcanzable tampoco serviría. Sin base configurada no hay barrido |
| P12 | ¿Se añade un tiempo máximo por análisis que mate al trabajador colgado? Exige `terminate_workers()` (Python 3.14 como mínimo) o API privada | No en este ticket: un ticket propio que suba el mínimo a 3.14, que ya usan `uv run` (3.14.3) y CI |
| P13 | ¿Se acepta el `lifespan` como única corrutina, delegando todo a `run_in_threadpool`? | Sí; se anota en ADR-037 |
| P14 | ¿Se confirma `PA-15.1` (un error por celda)? | Sí: es lo que devuelve el lector y TKT-018 pagina |
| P15 | Escenarios 28 y 29 en HDU-001 | **Aprobada.** Se ejecuta en la fila A-pre; los TC llevan `esc28` y `esc29` |
| P16 | Arranque sin variables de base (choque con el invariante CA-R4 y D-2 de TKT-006). Vías: **(a)** barrido y ejecutor solo con base configurada (`motor` pasado o las tres variables en el `entorno` recibido), y sin ella un aviso `trabajos_omitidos`; **(b)** mover las tres pruebas de `tests/test_servidor_arranque.py` a un entorno con base; **(c)** barrer en un comando de arranque aparte | **(a)**, que es la que este diseño recoge: sin base la aplicación no inicia sesión ni sirve nada de negocio, así que omitir con aviso no oculta un fallo real, y el invariante se conserva. (b) lo debilita y (c) añade un paso de despliegue olvidable |
| P17 | El progreso se cuantiza con `ROUND_DOWN` a mano, fuera de `Porcentaje.cuantizar()`, aunque la regla 1 dice que los tipos solo redondean con `cuantizar()`. ¿Se acepta como excepción `(asumido)`? | Sí: el progreso no es dinero ni columna de cálculo, y redondear hacia arriba un trabajo sin terminar sería mentir; la escala y el modo quedan escritos |

## Qué no se hace

- Ninguna ruta, esquema de respuesta ni pantalla (TKT-018), ni el `resumen` de previsualización.
- Nada de confirmar, materializar ni congelar (TKT-017); ninguna escritura en `concepto`, `insumo`, `linea_base` ni sus hijas.
- No se amplía ningún `CHECK`, no se toca el invariante 13 ni se resuelve `PA-T1`.
- No se crea la fila `importacion` ni se valida el archivo por sus bytes (TKT-018 y TKT-059); el adaptador del almacén de objetos es de TKT-059.
- No se asienta nada en la bitácora.
- No se añade un índice `(estado, latido)`, ni un tiempo máximo por análisis (P12), ni un barrido periódico: solo el de arranque.
- No se cambian los tiempos del rol de aplicación.
- No cambia lo que leen los lectores: solo se añade el aviso de avance, que no altera el resultado.
