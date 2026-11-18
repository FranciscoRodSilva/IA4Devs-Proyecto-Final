# Implementación · TKT-012b · Mantenimiento y ciclo de vida de la obra

> [← index](_index.md) | [← design](design.md)

Registro de la ejecución en curso. Se completa fila por fila con el ciclo TDD de metodología §16. Las salidas en rojo literales de cada fila viven en `rojo/fila-<N>.txt`.

## Modelo por paso

| Fila | Rojo | Verde | Motivo del modelo |
|---|---|---|---|
| A1 | `tester-backend` · `sonnet` | `desarrollador-sql` · `sonnet` | Disparador del diseño: reescribe `bitacora` con guarda de permanencia |
| A2 | `tester-backend` · `sonnet` | `desarrollador-dominio` · `haiku` | Por omisión; cerró al primer intento |
| A3 | `tester-backend` · `sonnet` | `desarrollador-sql` · `sonnet` | Disparador del diseño: bloqueo pesimista y consulta multitabla |
| A4 | `tester-backend` · `sonnet` | `desarrollador-aplicacion` · `haiku` | Por omisión; cerró al primer intento |
| A5 | `tester-backend` · `sonnet` | `desarrollador-aplicacion` · `sonnet` | Disparador del diseño: bloqueo, carrera con el congelado y asiento transaccional |
| A6 | `tester-backend` · `sonnet` | `desarrollador-aplicacion` · `sonnet` | Disparador del diseño: serialización de dos transiciones |
| A7 | `tester-api` · `sonnet` | `desarrollador-api` · `haiku` | Por omisión; cerró al primer intento |
| A8 | `tester-api` · `sonnet` | `desarrollador-api` · `haiku` | Por omisión; cerró al primer intento |
| A9 | `tester-backend` · `sonnet` | `desarrollador-aplicacion` · `haiku` | Disparador del diseño: concurrencia y mutación; el verde fue un arreglo mínimo por omisión |

## Entrega a

### A1 · Migración `0017` con el verbo `ELIMINAR` — Hecho

- **Rojo:** `8 failed, 0 errors` en `tests/test_tkt012b_migracion.py`; cada fallo por la razón esperada (falta la revisión `0017`, falta `AccionBitacora.ELIMINAR`, el valor no existe en el tipo). Salida literal en `rojo/fila-A1.txt`. La sonda del supuesto 1 confirmó con PostgreSQL real que usar el valor en la misma transacción que lo añade responde `55P04`.
- **Verde:** `8 passed` y `131 passed` en las pruebas ampliadas de `test_tkt007_*` y `test_tkt029b_*`. El ciclo `alembic upgrade head`, `downgrade -1` y `upgrade head` terminó sin error contra la base local.
- **Ampliaciones declaradas de pruebas existentes** (siete aserciones de 23 a 24 verbos): `test_tkt007_dominio.py:434`, `test_tkt007_fronteras.py:247`, `test_tkt007_esquema.py:262`, `:268` y `:543`, `test_tkt029b_migracion.py:270` y `test_tkt029b_api_baja.py:1414`.
- **Fuera de la lista del diseño, necesario:** el enum `AccionBitacora` de `docs/api/openapi.yaml` y el párrafo de verbos de `docs/03-modelo-datos.md` §10, porque `test_tkt007_esquema.py` compara la base con el borrador y la regla del modelo de datos exige que un verbo nuevo cambie el borrador en el mismo PR. El resto de los cambios del borrador sigue reservado a A7 y A8.
- **Orquestador:** el rojo del tester dejó un error `I001` de orden de imports en `test_tkt012b_migracion.py`; se corrigió con `ruff check --fix`, que solo reordena imports.
- **ADR:** `docs/adr/20261117-verbo-eliminar-y-borrado-fisico-de-la-obra.md`, con su entrada en el índice. El ADR no afirma el significado de `CANCELAR`, `ANULAR` y `DESCARTAR` en otros módulos; una persona debe confirmarlo en la revisión.

### A2 · Dominio del ciclo de vida y del historial — Hecho

- **Rojo:** `54 failed, 5 passed, 0 errors`. Los 54 fallan por `NotImplementedError` de esqueletos sin lógica. Los 5 verdes son guardas de pureza (TC-13) y la prueba de que las enums coinciden con `ck_obra_estado`; el tester demostró que muerden añadiendo un `import datetime` y un `float` y viéndolos fallar.
- **Verde:** `59 passed`; `ruff`, `verificar_float`, `lint-imports` (16 contratos, 0 rotos) y `mypy` en los dos módulos, limpios. Un error de `mypy` en el test del tester (`**{campo: 1}`) se devolvió al tester y se corrigió sin cambiar lo que comprueba.
- **Dos pruebas nacieron en verde** (`test_tkt012b_ca1_clave_desconocida_se_ignora` y `..._solo_claves_desconocidas_devuelve_vacio`): son de caracterización de una conducta que el desarrollador ya había implementado, añadidas después del verde a petición del orquestador. No sostienen un rechazo nuevo.
- **Trazabilidad que revisar:** en el PRD, `RN-25` es el tratamiento del IVA por obra; la spec la usa para la edición de los parámetros de la obra, y la máquina de estados sale de las decisiones D-2 y D-3 de la spec, no de una `RN`. Los docstrings lo dicen. La persona revisora debe confirmar que la cita basta.
- `D-DIS-5` queda marcada `(asumido)` en el docstring de `historial_obra.py`: basta una fila de `linea_base`, aunque sea `BORRADOR`.

### A3 · Repositorio de la obra — Hecho

- **Rojo:** `28 failed, 11 passed, 0 errors` en `tests/test_tkt012b_repositorio_obra.py`; los 28 fallan por `NotImplementedError` del esqueleto. Los 11 verdes son las dos sondas del motor y nueve comprobaciones de restricciones de `0006`. Salida en `rojo/fila-A3.txt`.
- **Supuestos del diseño confirmados con PostgreSQL real:** (2) `SELECT … FOR UPDATE` sobre `obra` deja esperando al `INSERT` de una línea base hija, comprobado con `pg_blocking_pids`; (3) un `DELETE FROM obra` con una hija responde `23001` con la restricción `fk_linea_base_obra_id`, no `23503`. La fila no se detuvo ni se escaló.
- **Verde:** `39 passed`; la regresión de TKT-012a, `88 passed`; `ruff`, `mypy`, `lint-imports` y `verificar_float` limpios. `FOR UPDATE` lleva `of=obra` porque el motor rechaza el bloqueo sobre el lado nulable del `OUTER JOIN`. `precio_insumo` y `rendimiento_observado` no están mapeadas en `tablas.py` y se cuentan con `text()` enlazado.
- El mutante «sin `cuantizar()`» sobrevive y es equivalente: PostgreSQL redondea igual al guardar en `NUMERIC(9,6)`.

### A4 · Puerto de historial — Hecho

- **Rojo:** `24 failed, 11 passed, 0 errors`. Los 11 verdes son de forma (campo y parámetros opcionales) y de frontera (cuatro pruebas por AST y con `lint-imports`, incluida una que prueba que romper la frontera sí se detecta).
- **Verde:** `35 passed`; los `143` de `test_tkt012b_*` acumulados en ese momento, en verde. ADR `docs/adr/20261117-historial-de-obra-por-puerto-inyectado.md` con su entrada en el índice. `vale` y `markdownlint-cli2` no se ejecutaron sobre los ADR nuevos (no se verificó su disponibilidad): quedan para la revisión.

### A5 · Casos de uso `actualizar_obra` y `eliminar_obra` — Hecho

- **Rojo:** `37 failed, 1 passed, 0 errors`. Todos los fallos por `NotImplementedError`; el verde es la prueba de firmas. El tester validó los tests con una implementación de referencia temporal y ocho mutantes, cada uno puso en rojo al menos un test.
- **Verde:** `38 passed`; la regresión de `test_tkt012b_*`, `test_tkt012a*` y `test_tkt017*`, `893 passed`.
- **Preguntas abiertas para la persona dueña** (el diseño no las fija): (1) `eliminar_obra` no comprueba el estado, de modo que una obra `CERRADA` sin historial (por ejemplo, cerrada desde `PLANEACION`) puede eliminarse; (2) el `409 OBRA_CON_HISTORIAL` ofrece solo `SUSPENDER_OBRA` y `CERRAR_OBRA` filtradas por estado, como declara el borrador, de modo que desde `SUSPENDIDA` solo se ofrece cerrar; (3) los textos de los mensajes los fijaron los tests y el ejemplo del borrador no coincide, por lo que A8 debe alinearlos; (4) la fotografía del asiento `ELIMINAR` lleva las nueve claves del `CREAR`.
- A7 debe confirmar contra el borrador la ruta de reintento (`/api/v1/obras/{id}`, `DELETE`) que usa la traducción del error del motor.

### A6 · Casos de uso de las tres transiciones — Hecho

- **Rojo:** `26 failed, 1 passed, 0 errors`; tres fallan por aserción en TC-39 porque el hilo que espera el bloqueo termina antes de tiempo. Un mutante que lee el estado antes del `FOR UPDATE` hace caer las tres.
- **Verde:** `27 passed`; los `208` de `test_tkt012b_*` acumulados, en verde. El mensaje de «no admite esta operación» se unificó en la constante `MENSAJE_ESTADO_NO_PERMITE` (refactor).
- El asiento de las transiciones usa `regla_negocio="RN-25"` por consistencia con `actualizar_obra`; el diseño no fija una regla propia. Queda en la lista de trazabilidad por confirmar. **Corregido después, por la auditoría F002a:** los asientos de las transiciones y de `ACTUALIZAR` ya no citan `RN-25`.
- Las acciones del `409 ESTADO_NO_PERMITE_OPERACION` salen de `operaciones_admitidas` e incluyen `REACTIVAR_OBRA` desde `SUSPENDIDA`; A8 debe documentarlas en el borrador.

### A7 · API de obras: `ObraCambios` y cinco rutas — Hecho

- **Rojo:** `203 failed, 0 errors`: las cinco rutas no existían (`405` y `404`). El tester validó las pruebas con una implementación de referencia y cuatro mutantes. Comprobó con el manejador real que `extra_forbidden` llega como `422 VALIDACION` señalando el campo con el código `VALOR_NO_PERMITIDO`, lo que el diseño marcaba `(sin ejecutar)`.
- **Verde:** `202 passed, 1 failed` en la primera corrida. El fallo era una prueba intermitente del tester: dos asientos con el mismo `ocurrido_en` bajo el reloj de prueba congelado. Se devolvió al tester, que avanzó el reloj entre las dos transiciones; tres corridas seguidas dieron `203 passed`. `test_tkt057_csrf.py` y `test_tkt017_api_congelado.py` se ampliaron como declaraba el diseño (`CUERPOS_VALIDOS`, `IMPLEMENTADAS_DE_PRESUPUESTO` y el filtro de `x-tickets`).
- **Pregunta abierta para la persona dueña:** no existe asignación usuario–obra en el modelo; Director de Proyectos y Dirección General operan sobre todas las obras de la empresa, igual que en TKT-012a. No se inventó una comprobación.

### A8 · Borrador OpenAPI y tipos del cliente — Hecho

- **Rojo:** `16 failed, 18 passed, 0 errors`; los 16 fallos son de contenido del borrador. `npm run tipos:verificar` ya salía en rojo porque A7 añadió las rutas sin regenerar. El tester añadió `422` a `eliminar_obra` en el contrato: sale del `422` por `obra_id` que no es UUID, ya fijado por TC-52.
- **Verde:** `34 passed`; `663 passed` en la regresión de `test_tkt012b_*`, `test_tkt007*` y `test_tkt017_api_congelado.py`; `tipos:generar` y `tipos:verificar` al día. Se actualizaron también `docs/07-especificacion-api.md` y `docs/03-modelo-datos.md` §14 (subsección «Obra» con su máquina de estados).
- **Decisión del desarrollador a confirmar:** se quitó el `(asumido)` de la descripción de `actualizar_obra` en el borrador, porque la spec lo confirma como Must. El encabezado de `CA-4` de la spec conserva un `(asumido)` desfasado, ya resuelto por D-3.
- **Pendiente:** el diagrama `stateDiagram-v2` nuevo de `docs/03` no se validó en un navegador (`tools/extraer_mermaid.py` solo genera la página de comprobación).

### A9 · Concurrencia, regresión y mutación — Hecho

- **Rojo:** 45 pruebas nuevas en `test_tkt012b_concurrencia.py` (TC-55 a TC-60) y `test_tkt012b_regresion.py` (TC-61, TC-62, TC-INV-2 a TC-INV-5). Diez casos de TC-60 cayeron en rojo y revelaron un defecto de producción: `actualizar_obra` y `_transicionar` (suspender, reactivar y cerrar) no traducían el `55P03` del motor, de modo que un `lock_timeout` agotado respondía `500` en lugar de `409 CONCURRENCIA` con `BLOQUEO_VENCIDO`. Salida literal en `rojo/fila-A9.txt`. Las esperas sondean `pg_stat_activity` y `pg_blocking_pids`; no hay `sleep`.
- **Verde:** `desarrollador-aplicacion` envolvió ambas funciones en el mismo `try/except DBAPIError` de `eliminar_obra`, con la ruta y el método de cada operación. Resultado: `45 passed` en la fila y `490 passed` en `test_tkt012b_*`. `ruff`, `mypy` y `lint-imports` limpios. Las pruebas de TKT-012a pasan sin tocarse (`88 passed`).
- **Suite completa antes del arreglo:** `8 failed, 4136 passed, 26 skipped`; los fallos eran solo de TC-60. Se repite al cerrar la entrega.
- **Mutación:** los 13 mutantes del diseño se desdoblaron en 17 y se añadieron 6 propios; los 23 murieron. Protocolo cumplido: copia fuera del repositorio, huella SHA-256 idéntica al inicio y al final (`15fc1bbf…046b5`), un mutante a la vez. La tabla completa está en `mutacion-a9.md`. El diseño esperaba que TC-55 matara «ignora la línea base `BORRADOR`»; no ocurre, lo matan TC-12 y TC-47, y la causa queda documentada.
- **Efecto lateral que debe confirmar la persona dueña:** `traducir_error_del_motor` también convierte `23505`, `23503`, `23001` genéricos y `22003` en `409 CONFLICTO ESTADO_NO_PERMITE_OPERACION` en estas operaciones; antes salían como `500`. El `codigo` no es específico del caso.
- **Deuda anotada:** el `lambda` de `rechazo_vigente` está repetido en tres casos de uso.
- **Hallazgo para TKT-018:** `crear_importacion` no existe aún. Si el borrado de la obra gana la carrera, el `INSERT` en `importacion` falla con `23503`; quien implemente TKT-018 debe traducirlo a `404 NO_ENCONTRADO` o bloquear la obra, o responderá `500`.
- **Para la pantalla (entrega b):** una obra `PLANEACION` cuyo congelado gana la carrera queda `ACTIVA`; por eso el `409` de eliminar ofrece `SUSPENDER_OBRA` y `CERRAR_OBRA` en ese caso.

## Entrega b

### B1 · `fraccionAPorcentaje` y `soloLectura` — Hecho

- **Rojo:** `39 failed, 440 passed, 0 errors`; los 39 son los casos nuevos de TC-63 (34, cada uno por el esqueleto que lanza «no implementado») y de TC-64 (5, porque el componente ignoraba la opción). Los dos casos de TC-INV-6 nacen en verde por diseño, como regresión de `CA-R5`. Salida literal en `rojo/fila-B1.txt`.
- **Verde:** `479 passed` en toda la suite de Vitest, con `lint` y `typecheck` limpios. `fraccionAPorcentaje` usa `decimal.js` y devuelve `null` ante una entrada inválida, igual que `porcentajeAFraccion`; ese comportamiento es `(asumido)` y la persona dueña debe confirmarlo. El tope de tres dígitos enteros de la fracción espeja el de la función inversa y tampoco lo fija la spec.
- **Corrección del test:** una prueba del tester llamaba a `user.clear()` sobre un campo de solo lectura, cosa que `user-event` rechaza y que contradecía a otra prueba de la misma suite. Se devolvió al tester, que quitó esa llamada; comprobó con un mutante (sin `readOnly`) que el test sigue mordiendo y que el archivo de producción quedó idéntico por huella SHA-256.
- **Observación:** `typecheck` no avisa si falta declarar `soloLectura` en un tipo de campo, porque el arnés de la prueba lo añade con *spread*.

### B2 · Acciones, mutaciones y formulario de edición — Hecho

- **Rojo:** `86 failed, 483 passed, 0 errors` en tres archivos nuevos (`obras.acciones.test.ts`, `obras.mutaciones.test.ts`, `obras.edicion.formulario.test.ts`; TC-65 a TC-68). Salida literal en `rojo/fila-B2.txt`. Cuatro pruebas nacieron en verde por ser propiedades negativas («el esquema no declara `codigo`, `tipo_contrato` ni `estado`»); el tester demostró con un mutante que caen si esos campos se declaran.
- **Verde:** `569 passed` en toda la suite, con `lint` y `typecheck` limpios. Las mutaciones no invalidan la lista por sí mismas: lo hace quien las llama, como `crearObra`.
- **Decisión del orquestador, a confirmar:** el diseño pedía a la vez que `esquemaEdicionObra` no incluyera `codigo` ni `tipo_contrato` (TC-68) y que el formulario los mostrara de solo lectura (TC-70). Se resolvió con un esquema de vista (`esquemaVistaEdicionObra`) que extiende el de edición con esos dos campos opcionales solo para tipar `FormularioCatalogo`; nunca viajan al servidor.
- **A confirmar por la persona dueña:** una mutación de transición sin motivo devuelve `{ ok: false }` con un error local de tipo `GENERICO` y sin petición; ningún tipo del contrato de error encaja. Los roles que operan se repiten en tres sitios (`ROLES_QUE_OPERAN` ya está compartido entre pantalla y acciones).

### B3 · Columna «Acciones» y edición — Hecho

- **Rojo:** `16 failed, 573 passed, 0 errors`; cuatro pruebas de rechazo (lectores sin columna) nacieron en verde porque la columna aún no existía, y quedan cubiertas por el mutante «columna visible para todos los roles» del cierre. Salida en `rojo/fila-B3.txt`.
- **Verde:** `589 passed`; `PantallaObras.test.tsx:529` sigue en verde. El desarrollador dejó TC-72 en rojo porque la aserción del tester consultaba la tabla con el diálogo modal abierto (la tabla queda fuera del árbol de accesibilidad). Se devolvió al tester, que la corrigió con `hidden: true` y dos aserciones (la lista conserva el nombre y no contiene lo tecleado); el diálogo sigue siendo modal, como exige CA-11. Salida en `rojo/fila-B3-tras-verde.txt`.
- Hasta B4 los botones de Eliminar, Suspender, Reactivar y Cerrar se dibujaban sin acción.

### B4 · Motivo, confirmación y bloqueo `OBRA_CON_HISTORIAL` — Hecho

- **Rojo:** `35 failed, 590 passed, 0 errors` (28 de la pantalla, 4 de rótulos y 3 de TC-73b). **TC-73b** (el `409 ESTADO_NO_PERMITE_OPERACION` dentro del diálogo de motivo, tres casos) no figura en la tabla de TC del diseño: lo añadió el orquestador porque la línea 129 del diseño prescribe ese comportamiento y no tenía escenario de rechazo. Salida en `rojo/fila-B4.txt`.
- **Verde:** `625 passed`; `lint` y `typecheck` limpios. `CapturaMotivo` ganó una prop opcional `avisoEnLinea` (aditiva; sin ella se comporta igual). Se añadieron los rótulos «Suspender» y «Cerrar» a `ETIQUETAS_ACCION`.
- **Decisiones a confirmar:** el bloqueo de eliminar ofrece solo las acciones que la pantalla sabe ejecutar (`SUSPENDER_OBRA`, `CERRAR_OBRA`) y no pinta `VER_OBRA`, porque esta pantalla no tiene ficha de obra; el `409` de estado dentro del motivo no muestra acciones; los textos de los diálogos y de los avisos genéricos son `(asumido)`.

### B5 · Semilla de humo con congelado — Hecho

- **Rojo:** `10 failed, 12 passed, 0 errors` (los 10 de TC-80 por el `NotImplementedError` del esqueleto; los 11 de TKT-018a y una prueba de regresión nacieron en verde). Salida en `rojo/fila-B5.txt`. El mutante `congelar=True` por omisión hizo caer esa prueba y cinco de TKT-018a.
- **Verde:** `22 passed`; `ruff`, `mypy`, `lint-imports` y `verificar_float` limpios. La opción es la bandera `--congelar` y el parámetro `congelar`; si el congelado falla, la semilla termina con `SystemExit` y no imprime `OBRA_ID=` (el comportamiento es `(asumido)`, el diseño no lo fija). `preparacion-global.ts` siembra M1 (`E2E-M1-<sufijo>`, congelada) y M2 (`E2E-M2-<sufijo>`, borrador).
- **Decisión a confirmar:** los códigos llevan un sufijo aleatorio por corrida, no son fijos, porque `obra.codigo` es único y la base de humo acumula obras; es el patrón que ya usaba `E2E-LB`.
- **Riesgo 7 (la semilla congela con los datos sintéticos):** confirmado contra la base real por el E2E de B6, no solo con testcontainers.

### B6 · Prueba E2E de `CA-18` y wireframe — Hecho

- **E2E:** dos pruebas nuevas en `obras.spec.ts` (editar, suspender y reactivar la obra M1; eliminar la obra M2 con historial y ver el bloqueo `OBRA_CON_HISTORIAL`). Nacieron en verde porque la pantalla ya existía; se demostró que muerden con cinco mutantes, uno a la vez, con huella SHA-256 restaurada: cuatro mueren (lista sin refrescar, estado sin refrescar, bloqueo no reconocido, bloqueo sin acciones). `8 passed` en la suite de humo. Salida en `rojo/fila-B6.txt`.
- **Mutante superviviente, equivalente en el navegador:** anular la barrera de historial de `eliminar_obra` no se distingue desde la interfaz, porque la clave foránea produce el mismo `409 OBRA_CON_HISTORIAL`. Lo distingue TC-32 en el backend.
- **Wireframe 2b** actualizado en `docs/08-wireframes.md` (columna «Acciones», edición, motivo, confirmación y bloqueo; tabla de acciones por estado y rol).
- **Diferencia con la historia, decisión de la persona dueña:** `CA-16` dice que el bloqueo ofrece «Suspender y Cerrar», pero desde `PLANEACION`, donde se ofrece «Eliminar», el servidor solo envía «Cerrar» porque suspender exige una obra `ACTIVA`. El wireframe sigue el contrato; la redacción de la spec debe alinearse.
- **Observaciones ajenas:** `verificar_docs.py` avisó de un enlace roto de `tkt-032a/_index.md` hacia un `impl.md` que aún no existe (es de TKT-032a) y de 16 archivos con CRLF.

## Auditorías de cierre

### `auditor-sql` · REQUIERE CAMBIOS (un hallazgo menor) → deuda declarada

- **F001 (menor):** el diseño afirmaba que el conteo del historial usa índices por `obra_id` que ya existen. Es falso para `precio_insumo` y `rendimiento_observado` (y `solicitud_autorizacion` para el `DELETE`): no tienen índice por `obra_id`, así que el conteo y la comprobación de la clave foránea `ON DELETE RESTRICT` recorren esas tablas enteras. El auditor propone una migración aditiva `0018` con tres índices; **no se hizo** porque amplía el alcance del ticket. Se corrigió la frase del diseño y queda como deuda para la persona dueña (decidir si entra en este ticket o en uno posterior; `rendimiento_observado` crece con el avance).
- Se añadió a `docs/03-modelo-datos.md` §10 la frase que faltaba sobre la bajada de `0017`.
- **Qué verificó el auditor:** ciclo `alembic downgrade -1` y `upgrade head` contra la base local de desarrollo sin diferencias (cuenta, ACL de `bitacora`, índices, restricciones y huella de los 93 asientos idénticas); `accion_bitacora` con 23 verbos tras bajar y sin residuos del tipo auxiliar; el rol de aplicación ya tenía `DELETE` y `UPDATE` sobre `obra` desde `0006`; nueve claves foráneas hacia `obra`, todas `ON DELETE RESTRICT`; `FOR UPDATE OF obra` compilado correctamente; sin SQL interpolado; `232 passed` en `-k "esquema or migracion or permisos"` y `63 passed` en repositorio, migración y regresión. La guarda con asientos `ELIMINAR` la cubren las pruebas, no se ejecutó a mano en la base de desarrollo.
- **Observación sin acción:** `FOR UPDATE` también lo toman las ediciones y transiciones, aunque `FOR NO KEY UPDATE` bastaría; se mantiene por consistencia con el congelado de TKT-017.

### `auditor-arquitectura` · REQUIERE CAMBIOS (cinco hallazgos; ninguno rompe una regla con código que falle hoy)

Los hallazgos exigen una decisión de la persona dueña, así que **no se aplicó ninguna corrección**: el ciclo de corrección queda detenido hasta que decida (`/sdd-escalar`).

- **F001 (mayor): `archivos` ya escribe filas con `obra_id`.** El ADR del puerto de historial obliga a que el primer módulo que lo haga publique su `FuenteHistorialObra`, y `archivos` ya existe y está montado, pero `servidor/fabrica.py` pasa `fuentes_historial` vacío y la tabla `archivo` no tiene clave foránea hacia `obra`. Hoy `DELETE /api/v1/obras/{id}` borraría una obra con archivos y dejaría huérfanas las filas y los objetos del almacén. Corrección propuesta: `archivos` publica una fuente en su `interfaz.py`, la raíz de composición la pasa, y una prueba de composición comprueba obra con archivo → `409 OBRA_CON_HISTORIAL`.
- **F002a (mayor): cita de regla falsa en la bitácora permanente.** Los asientos de las transiciones y de `ACTUALIZAR` citan `RN-25`, que en el PRD es el tratamiento del IVA; la bitácora no admite `UPDATE`, así que la cita quedaría grabada. Corrección propuesta: `regla_negocio=None` (lo admite `asentar`) o citar `RN-25` solo cuando el cambio toca `iva_acreditable`. Cambia lo que asertan las pruebas de A5 y A6.
- **F002b (mayor, decisión humana): la máquina de estados no tiene `RN` en el PRD.** Solo la respaldan las decisiones D-2 y D-3 de la spec y `docs/03` §14. La persona que aprueba confirma si basta o si se añade una `RN` o un ADR.
- **F003 (menor): `traducir_error_del_motor` enmascara fallos inesperados.** Convierte `23505`, `23503`, `23001` genéricos y `22003` en `409 CONFLICTO ESTADO_NO_PERMITE_OPERACION` en las operaciones de obra, con mensajes que no aplican (por ejemplo «la preparación de la importación»), y el `55P03` habla de «la línea base» cuando se bloqueó la obra. Corrección propuesta: relanzar lo que no sea `55P03`, `57014` o el `23001` propio, o dar mensajes propios de obra.
- **F004 (observación): `eliminar_obra` no comprueba el estado.** Una obra `CERRADA` sin historial se borra por API aunque la pantalla solo ofrezca «Eliminar» en `PLANEACION`. Pregunta abierta desde A5.
- **F005 (observación):** el `lambda` de `rechazo_vigente` está repetido en tres sitios.
- **Qué verificó el auditor:** `lint-imports` (16 contratos, 0 rotos), `ruff`, `mypy` (372 archivos), `verificar_float` (0 hallazgos); `398 passed` en las pruebas de dominio, casos de uso, contrato y API de TKT-012b; lectura completa de los dos módulos de dominio (solo biblioteca estándar y `tipos_base`); ausencia de `float`, `async def`, `sqlite`, `create_all` y `passlib` en producción; bitácora asentada en la misma transacción y antes del `DELETE`; orden de bloqueo obra → línea base igual que el congelado de TKT-017; rutas `def` con `verificar_origen` y `exigir_rol`; `tipos:verificar` al día; 47 ADR coherentes con `CLAUDE.md` y `README.md`. No verificó `markdownlint-cli2`, `vale`, el diagrama Mermaid ni el E2E.

### Ciclo de corrección 1 · F001 y F002a — Hecho

La persona dueña aprobó aplicar ambos hallazgos. Se siguió el ciclo TDD: rojo con `tester-backend` (`rojo/fila-C1.txt`: `43 failed, 51 passed, 0 errors`) y verde con `desarrollador-aplicacion` (`haiku`).

- **F001:** `cimenta/archivos/infraestructura/fuente_historial.py` (`FuenteHistorialArchivos`, exportada por `cimenta/archivos/interfaz.py`) cuenta todas las filas de `archivo` de la obra con la sesión del llamador, y `servidor/fabrica.py` la pasa en `fuentes_historial`. `presupuesto` no importa `archivos`. Una obra con archivos responde ahora `409 OBRA_CON_HISTORIAL` en lugar de borrarse y dejar huérfanos los registros. Prueba de composición de extremo a extremo con la fábrica real.
- **F002a:** los asientos `ACTUALIZAR`, `SUSPENDER`, `REACTIVAR` y `CERRAR` asientan `regla_negocio=None`. `ELIMINAR` conserva `RN-01`. Se ampliaron, de forma declarada y por decisión de la persona dueña, las aserciones de `test_tkt012b_mantenimiento_obras.py` y `test_tkt012b_ciclo_vida_obra.py` que afirmaban `RN-25`.
- **Verde:** `94 passed` en los cuatro archivos y `796 passed` en `test_tkt012b_*`, `test_tkt012a*` y `test_tkt007*`; `ruff`, `mypy` (375 archivos), `lint-imports` (16 contratos) y `verificar_float` limpios.
- **`(asumido)`, a confirmar:** la fuente cuenta también los archivos `PENDIENTE` y `CADUCADO` (el barrido no borra filas y el rol de aplicación no puede borrarlas). Quedan docstrings de rutas con «RN-25, PA-02, PA-18» (`rutas_obras.py` líneas 50 y 114) que describen el endpoint, no el asiento, y no se tocaron.
- **Sin resolver:** F002b (la máquina de estados no tiene `RN` en el PRD), F003 (traductor de errores), F004 (eliminar una obra `CERRADA` sin historial) y F005 (duplicación del `lambda`) siguen como observaciones para la persona dueña.

### Reauditoría de `auditor-arquitectura` · APROBADO

F001 y F002a quedan resueltos sin violaciones nuevas. **Qué verificó el auditor:** `lint-imports` (16 contratos, 0 rotos) y ausencia de importaciones de `archivos` desde `presupuesto`; consulta enlazada que usa la sesión del llamador sin confirmar y que se ejecuta después del `FOR UPDATE` y antes del `DELETE`; asientos con `regla_negocio=None` en `ACTUALIZAR`, `SUSPENDER`, `REACTIVAR` y `CERRAR`, y `RN-01` en `ELIMINAR`; 24 verbos coherentes entre enumeración, borrador y pruebas; `ruff`, `mypy` (375 archivos) y `verificar_float` limpios; `29 passed` en las pruebas puntuales de la corrección. Observaciones menores sin bloqueo: los docstrings de TC-33 y TC-37 aún nombran `RN-25` para las transiciones (alinear con F002b) y quedan las citas de `RN-25` como regla del endpoint de alta y edición, que es legítima para el IVA.

## Revisión (`/sdd-revisar`) — en curso

### Reauditoría de `auditor-sql` · APROBADO, con una condición para `/sdd-completar`

El hallazgo F001 de `auditor-sql` (índices por `obra_id` que no existen) queda **resuelto**: el diseño ya no afirma lo falso y `docs/03-modelo-datos.md` §10 trae la frase sobre la bajada de `0017`. No hay hallazgos nuevos. Para no confundirlo con el F001 de `auditor-arquitectura` (la fuente de historial de `archivos`), debe citarse siempre con el prefijo del auditor.

**Condición:** `delta.md` debe formalizar la deuda con su alcance completo: faltan índices por `obra_id` en `precio_insumo`, `rendimiento_observado` y `solicitud_autorizacion`, y afectan tanto al conteo del historial como a la comprobación de la clave foránea en el `DELETE`. La persona dueña decide si la migración `0018` entra en este ticket o en uno posterior.

**Qué verificó el auditor:** índices existentes y ausentes contra la base viva (`pg_indexes`); la frase de `0017` en `docs/03` línea 1014; que `v0017` y `repositorio_obra.py` no cambiaron desde la primera auditoría (por marca de tiempo, no por huella de contenido); ciclo `downgrade -1` y `upgrade head` en la base local, con 93 asientos y un único tipo `accion_bitacora` al terminar y la base de nuevo en `0017 (head)`.

### Estado de las demás auditorías

`auditor-seguridad` y `auditor-docs` quedaron interrumpidos por el límite de uso de la cuenta (se reanuda a las 20:40, hora de Ciudad de México); `auditor-codigo` sigue en curso. El cierre de la revisión espera sus veredictos.

### Ciclo de corrección 2 · hallazgos de `auditor-codigo`, `auditor-seguridad` y `auditor-docs` — Hecho

- **Rojo** (`rojo/fila-C2.txt`: `8 failed, 18 passed`): cuatro pruebas de `CWE-209` (el `409 OBRA_CON_HISTORIAL` por clave foránea publicaba `restriccion`, el nombre interno de la clave) y cuatro de F005 (el reloj se leía antes de esperar el bloqueo). Tres aserciones existentes se ampliaron por decisión de seguridad y quedaron declaradas; nace además una guarda parametrizada de 18 casos que comprueba que ningún rechazo de las cinco operaciones contiene `fk_` ni `restriccion` y que cada error valida contra el borrador.
- **Verde** con `corrector-revision` (`haiku`): el `detalle` del `409` por clave foránea pasa a la forma del contrato con `movimientos: 1`, el reloj se lee dentro de la transacción tras el bloqueo, y se eliminan las duplicaciones (`traducir_fallo_de_obra`, `acciones_de_operaciones`, `transicionar`, `pintarRechazo`, campos editables derivados).
- **Prueba intermitente corregida:** `test_tkt012b_tc80_ca18_semilla_con_congelar_...` ordenaba los asientos por `ocurrido_en` e `id` bajo un reloj fijo, y el desempate por `uuid4` era aleatorio; el tester la corrigió y pasó cinco corridas seguidas.
- **Deuda declarada por la persona dueña, sin corrección en este ticket:** F007 (extraer `useMantenimientoObra` de `PantallaObras`, 467 líneas), O001 (justificar el cast de `sinSoloLectura` y probar una casilla de solo lectura), O002 (el `PATCH` envía siempre los seis campos), O003 (`FuenteHistorialObra.nombre` solo lo lee un test), el lambda duplicado de `obras.py` (TKT-012a), y el patrón `detalle={"restriccion": …}` que conserva el traductor genérico para otras operaciones (observación F005 de `auditor-seguridad`).
- **Observación nueva a documentar:** `movimientos: 1` en el `409` por clave foránea es un valor mínimo, no un conteo medido (`auditor-codigo N001`).

## Verificación final · entregas a y b

**Suite, copiada de la última corrida (tras el ciclo 2):**

| Comprobación | Resultado |
|---|---|
| `uv run pytest` (`rojo/suite-completa-final.txt`) | `4206 passed, 26 skipped in 1125.85s (0:18:45)` |
| `npm test` (Vitest) | `Test Files 31 passed (31)`, `Tests 625 passed (625)` |
| `npm run lint`, `npm run typecheck`, `npm run tipos:verificar` | limpios · «Tipos al día» |
| `ruff check`, `ruff format --check`, `mypy`, `lint-imports`, `verificar_float` (backend) | `All checks passed!` · 375 archivos formateados · `no issues found in 375 source files` · `16 kept, 0 broken` · `0 hallazgos` |
| `python tools/verificar_docs.py` | solo el enlace roto de `tkt-032a/_index.md → impl.md` (de otro ticket) y el aviso CRLF/LF conocido |
| `python -m unittest discover -s tools/tests` | `Ran 518 tests … OK` |
| E2E de humo (`npm run e2e`, repetido tras el ciclo 2; `rojo/e2e-final.txt`) | `8 passed (20.2s)` |

**Criterios:** `CA-1` a `CA-18` y `CA-R1` a `CA-R5` tienen pruebas nombradas con su escenario (backend, Vitest y E2E) y su salida de rojo por fila (`rojo/fila-A1.txt` a `fila-C2.txt`). Hay rechazo con contrato completo para cada regla implicada. Mutación: 23 mutantes en A9 y 5 en el E2E, con la tabla en `mutacion-a9.md`.

**Veredictos finales:**

| Auditor | Veredicto |
|---|---|
| `auditor-arquitectura` | `APROBADO` (reauditoría del ciclo 1; el ciclo 2 solo se refactorizó sobre el mismo diff, con sus 4206 pruebas en verde) |
| `auditor-sql` | `APROBADO`, con una condición: `delta.md` debe declarar la deuda de los índices por `obra_id` con su alcance completo |
| `auditor-codigo` | `APROBADO` |
| `auditor-seguridad` | `APROBADO` (`pip-audit` no pudo correr sin red; las dependencias no cambiaron) |
| `auditor-docs` | `APROBADO` |

**Señalado a la persona que aprueba:** el PR toca `docs/api/openapi.yaml` (cinco operaciones nuevas, `ObraCambios`, verbo `ELIMINAR`, `409` y `422`).

**Pendientes de la persona dueña, sin bloquear la revisión:** F002b (la máquina de estados no tiene `RN` en el PRD), F003 de `auditor-arquitectura` (el traductor genérico convierte fallos inesperados en `409 ESTADO_NO_PERMITE_OPERACION`), F004 (eliminar una obra `CERRADA` sin historial), la migración `0018` de índices (decidir si entra aquí o después), los supuestos `(asumido)` marcados en cada fila y las cuatro preguntas de A5 y A7.
