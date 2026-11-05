# Trabajos en dos pasos: el API gobierna el latido, un proceso hijo parsea y un barrido de arranque cierra lo interrumpido

## Estado

Aceptado

## Contexto y problema

TKT-015 analiza el Excel de línea base sin bloquear la petición. Parsear un libro real (miles de conceptos con `openpyxl`) ocupa la CPU durante decenas de segundos; hacerlo en un hilo del propio proceso del API retiene el intérprete (GIL) y degrada a todas las demás rutas, que son `def` y viven en el mismo grupo de hilos ([ADR-013](20260919-sqlalchemy-sincrono.md)). El análisis debe además dejar rastro de que sigue vivo (`importacion.latido`), informar cuánto avanzó (`importacion.progreso`) y, si el proceso muere a medias, no dejar la obra con una importación en `ANALIZANDO` para siempre: mientras haya una importación activa, el resto de la obra no puede iniciar otra.

Cuatro decisiones quedan abiertas:

1. **Quién escribe el latido.** El latido existe para que el barrido distinga «sigue vivo» de «murió».
2. **Cuántos análisis corren a la vez.** Cada uno carga un libro completo en memoria.
3. **Dónde vive el barrido genérico** que marca vencidas las filas en estado intermedio. `TKT-059` lo reutilizará para otros estados.
4. **Qué hace el arranque si no hay base configurada.** TKT-006 fijó que la aplicación arranca sin variables de base (invariante `CA-R4`), y varias pruebas de `tests/test_servidor_arranque.py` lo ejercitan.

## Opciones consideradas

### Quién escribe el latido

| | El hijo, con su conexión | El proceso del API (elegida) |
|---|---|---|
| Qué dice el latido | «El hijo está vivo» | «El API gobierna el trabajo y el hijo no ha muerto» |
| Conexión a la base | El hijo abre la suya y necesita credenciales y el rol de aplicación | El hijo **no toca la base de datos** |
| Trabajos en cola | No laten: no tienen proceso | Laten también, porque el API sabe que esperan turno |
| Muerte del hijo | El latido se detiene solo | El despachador detecta `BrokenProcessPool` y cierra la importación |
| Trabajo colgado en un bucle | El hijo sigue latiendo | **El API sigue latiendo**: el latido no distingue colgado de lento (consecuencia declarada) |

### Cuántos análisis a la vez

| | Varios en el grupo | Uno a la vez (elegida) |
|---|---|---|
| Memoria | Varios libros cargados | Un libro |
| Muerte del trabajador | `BrokenProcessPool` hace fallar **todos** los futuros, incluidos los que esperaban | Solo falla el que corría; los que esperaban se reenvían a un grupo nuevo |
| Latencia de un trabajo corto tras uno largo | Menor | Mayor, aceptada: el análisis se hace una vez por libro |

### Dónde vive el barrido

| | `servidor/` | Módulo nuevo en `cimenta/` | `tipos_base/` | Paquete propio `trabajos/` (elegida) |
|---|---|---|---|---|
| Puede importarlo `TKT-059` sin acoplarse a `presupuesto` | No: `servidor/` es raíz de composición y nada la importa | No: rompe `esqueleto-modulos` (diez módulos, ni uno más) | No: `tipos_base/` admite solo la biblioteca estándar y el barrido necesita `sqlalchemy` | Sí |
| Frontera vigilada | La prueba de pureza no existe | `import-linter` | `import-linter` | `import-linter`, con contrato propio |

### Qué hace el arranque sin base (P16)

| | Barrer siempre | Mover las pruebas a un entorno con base | Omitir sin base configurada, con aviso (elegida) |
|---|---|---|---|
| Invariante `CA-R4` de TKT-006 | Se rompe: sin variables, `fastapi dev` no levanta | Se debilita: las pruebas dejan de ejercer el arranque mínimo | Se conserva |
| Un fallo real queda oculto | No | No | No: sin base la aplicación no inicia sesión ni sirve nada de negocio |

## Decisión

### 1. El proceso del API gobierna el trabajo y refresca el latido

Un **hilo despachador** del proceso del API, único dueño del estado del ejecutor, saca un trabajo de la cola, lo envía a un `ProcessPoolExecutor` y, cada `CIMENTA_TRABAJOS_INTERVALO_LATIDO` segundos, hace tres cosas, cada una en una transacción corta: refresca `importacion.latido` **del trabajo en curso y de los que esperan turno**, vacía de una cola compartida el avance que el hijo informa y lo guarda en `importacion.progreso`, y, cuando el futuro termina, cierra la importación por el caso de uso. El **hijo parsea y nada más**: recibe bytes y un mapa de insumos, devuelve un resultado. No abre conexión, no conoce al repositorio y no escribe la bitácora.

### 2. Un solo trabajo a la vez, en un grupo de un solo trabajador `spawn`

`ProcessPoolExecutor(max_workers=1)` con contexto `spawn` (no `fork`: el hijo no debe heredar conexiones ni hilos del padre). El despachador envía **un** trabajo y espera su futuro antes de enviar el siguiente. Si el trabajador muere (`BrokenProcessPool`), el despachador marca interrumpida **solo** esa importación con el motivo `TRABAJADOR_TERMINADO`, crea un grupo nuevo y sigue con la cola. El ejecutor es perezoso: construirlo no crea procesos ni hilos; nacen en el primer `encolar`, para que las pruebas que levantan la aplicación no paguen el arranque de un proceso.

### 3. `trabajos/` como paquete raíz, con contrato de lista blanca

`backend/trabajos/` queda **fuera de `cimenta/`**, al lado de `tipos_base/`, y se añade a `root_packages`. Su contrato es el de `tipos_base/`, una lista blanca con `permitidos = ["sqlalchemy"]` y no el de `contrato_error/`, que se protege con una prueba de pureza. La lista blanca es la forma correcta porque lo que se quiere impedir es «cualquier cosa que no sea la biblioteca estándar y `sqlalchemy`», directa o indirectamente; una lista `forbidden` tendría que enumerar `cimenta`, `servidor`, `fastapi`, `pydantic` y todo lo que se añada mañana. `trabajos.barrido` expone `DefinicionBarrido` (tabla, estados intermedio y vencido, columna de marca, umbral y la función `al_vencer`) y `barrer_todas`. **No conoce a quien lo define**: la definición de las importaciones la construye `presupuesto` y la pasa `servidor/`, que es la raíz de composición. El contrato lo impone `import-linter` (`trabajos-solo-sqlalchemy`), y mypy estricto cubre `trabajos.*`.

[ADR-022](20261020-contrato-de-error-y-raiz-de-composicion.md) descartó «por ahora» añadir `contrato_error/` y `servidor/` a `root_packages` con contratos propios, porque cambiaba el total de contratos y obligaba a reescribir las pruebas de TKT-004, y dejó esa puerta abierta «si otro ticket la reclama». TKT-015b la reclama para `trabajos/`: un paquete con dependencia externa (`sqlalchemy`) necesita que `import-linter` vea sus importaciones, y la prueba de pureza de `contrato_error` solo sabe de la biblioteca estándar. Se actualizan las tres suites de fronteras y el total de contratos.

### 4. El barrido corre en el `lifespan`, antes de servir, si hay base configurada

Al arrancar, el `lifespan` de `servidor/fabrica.py` ejecuta `barrer_todas` con la definición de las importaciones: las que están en `ANALIZANDO` con `latido` nulo o más viejo que `CIMENTA_TRABAJOS_UMBRAL_VENCIMIENTO` pasan a `CON_ERRORES` con un error `PROCESO_INTERRUMPIDO` (motivo `REINICIO`), en la misma transacción. El umbral es al menos tres veces el intervalo. Con la base configurada, **un barrido fallido impide arrancar** (P11): con una base inalcanzable la aplicación tampoco serviría. Al cerrar ordenadamente, el `lifespan` llama a `ejecutor.cerrar()`, que interrumpe la cola y el trabajo en curso con `REINICIO` antes de apagar el grupo de procesos. Una **muerte brusca** del API (sin ejecutar el `finally` del `lifespan`) sigue dependiendo del barrido del arranque siguiente.

### 5. Sin variables de base no hay barrido ni ejecutor (P16)

Si no hay `motor` pasado ni las tres variables de base en el entorno recibido, el `lifespan` no barre, no crea el ejecutor y registra el aviso `trabajos_omitidos`. `app.state.ejecutor_analisis` queda en `None`; TKT-018 lo trata en su dependencia. Esto conserva el invariante `CA-R4` de TKT-006 y las pruebas de arranque sin base.

### 6. Un trabajo colgado mantiene su latido mientras viva el API (P12)

Como el latido lo escribe el API, un trabajo que se cuelga dentro del hijo **sigue latiendo** y su importación nunca vence. La obra queda sin poder iniciar otra importación hasta reiniciar el servicio, y el reinicio lo resuelve porque el barrido del arranque cierra lo interrumpido. Un tiempo máximo por análisis exige `terminate_workers()` (Python 3.14 como mínimo) o una API privada de `concurrent.futures`; este ticket **no** lo incluye y la recomendación es un ticket propio que suba el mínimo a 3.14, versión que ya usan `uv run` y CI.

### 7. El `lifespan` es la única `async def` del backend: excepción a la regla 11 y a ADR-013

[ADR-013](20260919-sqlalchemy-sincrono.md) y la regla 11 de `CLAUDE.md` dicen «nunca `async def`». FastAPI admite hoy un `lifespan` solo como corrutina (`asynccontextmanager`). La excepción es **una**, la del `lifespan`, y su cuerpo solo delega con `run_in_threadpool` en el barrido, la creación del ejecutor y su cierre: no ejecuta una sola llamada bloqueante dentro de la corrutina. Las rutas siguen siendo `def`. Esta decisión anota la excepción para que la regla no quede contradicha.

### 8. El progreso se redondea con `ROUND_DOWN`, fuera de `cuantizar()` `(asumido)`

`progreso_de_lectura(hojas_leidas, hojas_totales)` calcula la fracción de lectura con escala 6 y `ROUND_DOWN`, acotada a 0.9 mientras el análisis no termina: el cierre fija 1. No usa `Porcentaje.cuantizar()`, que redondea con `ROUND_HALF_UP` ([ADR-020](20261019-tipos-numericos-base.md)): un trabajo que no terminó no debe redondear hacia arriba (`(4, 7)` da `0.514285`, no `0.514286`). La regla 1 de `CLAUDE.md` dice que los tipos solo redondean con `cuantizar()`; esta es una excepción **`(asumido)`**, aprobada en la pregunta P17 del diseño: el progreso no es dinero ni una columna de cálculo, y la escala y el modo van escritos en la función. Ninguna cifra monetaria usa este camino.

### 9. El hijo `spawn` no lo mide `pytest-cov`

El código que corre solo en el proceso hijo (`ejecutar_en_trabajador`, `notificar_avance`, `_iniciar_trabajador`, unas diez líneas) queda fuera del informe de cobertura: `pytest-cov` mide el proceso de la prueba. Lo ejercitan las pruebas del ejecutor (TC-52 a TC-62) con un hijo real. `analizar_contenido` sí se mide, porque sus pruebas lo ejecutan en el proceso de la prueba. El pipeline añade `--cov=trabajos` y una prueba de `tools/tests/test_definicion_ci.py` la exige.

## Consecuencias

**Positivas**

- El API sigue respondiendo mientras un libro se parsea: el trabajo pesado no comparte el GIL con las rutas.
- Una importación abandonada por un reinicio, una caída o la muerte del hijo se cierra sola con un error visible, y la obra puede reintentar.
- La muerte del trabajador afecta a un solo análisis.
- `TKT-059` reutiliza `trabajos.barrido.DefinicionBarrido` con `columna_marca="creado_en"` sin depender de `presupuesto`.

**Negativas o costes aceptados**

- Un trabajo colgado en el hijo mantiene su latido y bloquea la obra hasta reiniciar (P12).
- Los trabajos se serializan: un libro largo retrasa al siguiente.
- Un reinicio brusco del API (sin `finally` del `lifespan`) deja las importaciones en curso hasta el barrido del arranque siguiente, que puede tardar hasta el umbral en considerarlas vencidas. Un apagado ordenado las marca con `REINICIO` al cerrar el ejecutor.
- El `lifespan` es la única corrutina del backend y exige disciplina: todo lo bloqueante pasa por `run_in_threadpool`.
- Con la base configurada, `fastapi dev` y `fastapi run` exigen la base arriba y migrada: un barrido fallido impide arrancar.
- Sin variables de base no hay barrido ni ejecutor, y las rutas que lo necesiten deben comprobarlo.
- El código del hijo queda sin medir en cobertura.
- El progreso se redondea con una excepción `(asumido)` a la regla 1.

**Cuándo revisar esta decisión**

- Si aparece un tiempo máximo por análisis (ticket propio, Python 3.14 como mínimo): el latido del API podría dejar de bastar.
- Si un segundo trabajo pesado (nómina, destajo) necesita ejecutarse en paralelo con las importaciones.
- Si la fase 2 incorpora un orquestador de trabajos externo que sustituya al despachador.
