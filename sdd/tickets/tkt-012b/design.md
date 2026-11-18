# Design · TKT-012b · Mantenimiento y ciclo de vida de la obra

> [← index](_index.md) | [← spec](spec.md) | Siguiente: [impl →](impl.md)

## Estrategia

El ticket completa la obra con cinco operaciones del borrador OpenAPI (`actualizar_obra`, `eliminar_obra`, `suspender_obra`, `reactivar_obra`, `cerrar_obra`) y con sus acciones en la pantalla «Obras». Todo el razonamiento de negocio vive en dos funciones puras de `dominio/` —la máquina de estados del ciclo de vida y la decisión de «¿tiene historial?»— y los casos de uso solo las orquestan dentro de una transacción que toma primero `SELECT … FOR UPDATE` de la fila de la obra, en el mismo orden que ya usa el congelado de TKT-017 (obra, luego línea base). Esa fila bloqueada es lo que serializa dos transiciones simultáneas, y lo que hace que un borrado y una escritura de otro módulo no se crucen.

El «historial» es amplio (decisión D-1). La parte de `presupuesto` se cuenta con consultas propias sobre sus tablas. La parte de los módulos posteriores no puede importarse: `presupuesto` es el núcleo y ningún módulo de negocio está en su grafo de importación. Por eso el caso de uso depende de un **puerto** definido en `presupuesto` (`FuenteHistorialObra`), que `servidor/` —la raíz de composición— rellena con las interfaces publicadas de los módulos que lo publiquen. Hoy ningún módulo lo publica, así que la tupla de fuentes va vacía y el conteo de movimientos es cero; la clave foránea `ON DELETE RESTRICT` de cada tabla hija que ya existe (`requisicion`, `orden_compra`, `solicitud_autorizacion`, migración `0014`) queda como última barrera y se traduce a `OBRA_CON_HISTORIAL` (ver D-DIS-4).

El borrado es físico y su asiento lleva el verbo nuevo `ELIMINAR`, que añade la migración `0017` con el mismo molde que `0016` (`ADD VALUE` en la subida, bajada con guarda que recrea el tipo). El trabajo se parte en dos entregas, **a** (backend, filas A1 a A9) y **b** (pantalla y prueba de extremo a extremo, filas B1 a B6), que se acumulan en una sola rama y salen en **un solo PR**.

## Escalera de decisión

| Objeto | Peldaño donde paró | Por qué |
|---|---|---|
| Rutas `PATCH`/`DELETE`/`POST …/suspension\|reactivacion\|cierre` en `rutas_obras.py` | 4 · cambio mínimo | El enrutador de obras ya existe (TKT-012a) y el borrador ya declara las cinco operaciones; se añaden al mismo archivo, sin enrutador nuevo |
| `ObraCambios` (DTO del `PATCH`) | 5 · objeto nuevo | `ObraNueva` ignora campos desconocidos y exige todos; el `PATCH` debe **rechazar** `codigo`, `tipo_contrato` y `estado` (`CA-2`), aceptar un subconjunto y distinguir `umbral_alerta_pct: null` (borrar) de ausente. Ningún DTO existente lo cubre |
| Cuerpo con motivo de las tres transiciones | 3 · reuso | `Motivo` (`MotivoTexto`: sin espacios en los extremos, 1 a 2000 caracteres, sin `NUL`) ya lo definió TKT-017 |
| `ROLES_MANTENIMIENTO` | 3 · reuso | Son los mismos dos roles que `ROLES_ALTA`; se usa esa constante, no se crea otra |
| Función pura `evaluar_transicion` y `operaciones_admitidas` (`dominio/ciclo_vida_obra.py`) | 5 · objeto nuevo | Ninguna regla existente modela el ciclo de vida. Lo que ya existe, `evaluar_congelado`, solo conoce la arista `PLANEACION → ACTIVA` y no se toca (`CA-R1`) |
| Función pura `admite_edicion` | 5 · objeto nuevo (mismo archivo) | Una línea con nombre: «solo `CERRADA` bloquea» queda escrita una vez, con su test |
| Función pura `cambios_efectivos` | 5 · objeto nuevo (mismo archivo) | Decide qué campos cambian de verdad (sin asiento si ninguno, `S-2`) y construye el antes y el después de la bitácora |
| Función pura `hay_historial` (`dominio/historial_obra.py`) | 5 · objeto nuevo | La definición amplia de D-1 es una regla de negocio y no debe quedar escondida en una consulta SQL |
| Puerto `FuenteHistorialObra` (`aplicacion/historial_obra.py`) y campo `fuentes_historial` en `ContextoPresupuesto` | 5 · objeto nuevo | Peldaño 4 (importar `compras`) rompe `grafo-presupuesto`; peldaño 1 (ignorar los módulos posteriores) deja el borrado inseguro cuando existan sus filas. Es el único objeto no trivial; ver ADR |
| `bloquear_obra_completa`, `actualizar_obra`, `cambiar_estado_obra`, `eliminar_obra`, `contar_historial_propio` en `repositorio_obra.py` | 4 · cambio mínimo | El repositorio de la obra ya existe; `repositorio_linea_base.bloquear_obra` solo devuelve cuatro columnas y vive en otro repositorio |
| `repositorio_linea_base.activar_obra` (congelado) | — · no se toca | Es la arista `PLANEACION → ACTIVA` de `PA-T17.8`; `CA-R1` la protege |
| Valor `ELIMINAR` en `accion_bitacora` (migración `0017`) | 5 · objeto nuevo | `CANCELAR`, `ANULAR` y `DESCARTAR` significan otra cosa (D-4, resuelta) |
| Bajada de `0017` con guarda y recreación del tipo | 3 · reuso | Es el patrón de la bajada de `0016`, sin variantes |
| Tablas, columnas, índices y disparadores nuevos | 1 · YAGNI | La obra ya tiene `estado`, `actualizado_en` y `actualizado_por_id`; `ck_obra_estado` ya limita los valores. **No** se añade un disparador de transiciones: el congelado escribe `ACTIVA` por su propio camino y la serialización la da el `FOR UPDATE` (ver riesgo R-3) |
| `soloLectura` opcional en los campos de `FormularioCatalogo` | 4 · cambio mínimo | Aditivo y con valor por omisión; las pruebas existentes no cambian (`CA-R5`). El formulario ya sirve de edición porque recibe `valoresIniciales` y `alGuardar` |
| Captura de motivo y confirmación de eliminación | 3 · reuso | `CapturaMotivo` y `ConfirmacionBaja` (TKT-008c y TKT-029b); el bloqueo se pinta con `ConflictoEnLinea` |
| Columna «Acciones» y `accionesDeFila` | 5 · objeto nuevo (mínimo) | Una función pura estado × rol → lista de botones (cortesía de navegación, `PA-T8`); el cliente no evalúa ninguna regla: el servidor sigue siendo la autoridad |
| `fraccionAPorcentaje` en `dinero.ts` | 5 · objeto nuevo (mínimo) | La edición precarga «15» desde la fracción `0.150000`; hoy solo existe la conversión inversa (`porcentajeAFraccion`). Aritmética de cadena, sin `Number` |

> Ningún objeto paró en el peldaño 4 tocando un invariante registrado. `repositorio_obra` y el enrutador cambian, pero ninguno de los 39 invariantes ni las 17 reglas de `CLAUDE.md` se ve estorbado: la regla 4 (línea base inmutable) se respeta porque el borrado solo procede cuando no existe ninguna línea base de la obra, y la regla 8 porque cada operación asienta en la misma transacción.

## Capas afectadas

### Dominio

| Archivo | Qué | Regla |
|---|---|---|
| `backend/cimenta/presupuesto/dominio/ciclo_vida_obra.py` (nuevo) | `EstadoObraDominio` (`StrEnum` de los cuatro estados), `OperacionObra` (`SUSPENDER`, `REACTIVAR`, `CERRAR`), `evaluar_transicion(estado, operacion) -> TransicionAdmitida \| TransicionRechazada` (el rechazo trae el estado actual y las operaciones que sí admite), `operaciones_admitidas(estado)`, `admite_edicion(estado)` y `cambios_efectivos(actuales, propuestos)` | `RN-25`, `PA-02`, `PA-18`; HDU-001 esc. 20 |
| `backend/cimenta/presupuesto/dominio/historial_obra.py` (nuevo) | `ConteosHistorial` (lineas base, línea base congelada sí/no, importaciones, filas propias de otras tablas de la obra, movimientos de módulos posteriores) y `hay_historial(conteos) -> bool` | `RN-01`; HDU-001 esc. 20 |

La tabla de transiciones que `evaluar_transicion` aplica es exactamente la de D-2:

| Origen | `SUSPENDER` | `REACTIVAR` | `CERRAR` |
|---|---|---|---|
| `PLANEACION` | rechaza | rechaza | admite → `CERRADA` |
| `ACTIVA` | admite → `SUSPENDIDA` | rechaza | admite → `CERRADA` |
| `SUSPENDIDA` | rechaza | admite → `ACTIVA` | admite → `CERRADA` |
| `CERRADA` | rechaza | rechaza | rechaza |

`PLANEACION → ACTIVA` no figura aquí a propósito: solo ocurre por el congelado (`evaluar_congelado` exige `PLANEACION`), nunca por una de las tres operaciones. La función `operaciones_admitidas` es la fuente de las `acciones` del `409` `OBRA_CON_HISTORIAL` y de `ESTADO_NO_PERMITE_OPERACION` (objeción 5 de la spec).

`hay_historial` es verdadera si **cualquiera** de estos conteos es mayor que cero: filas de `linea_base` (cualquier estado), de `importacion`, de `nivel`, de `concepto`, de `precio_insumo` o de `rendimiento_observado` de esa obra, o los movimientos que reporten los módulos posteriores. `presupuesto_control` cuelga de la línea base, así que queda cubierto por ella. Ninguna ruta del producto crea una línea base vacía (la materialización la crea con su jerarquía; el congelado, con sus copias y su control), así que «línea base no vacía de cualquier estado» y «existe una fila de `linea_base`» coinciden hoy; la segunda forma es la que se consulta (ver D-DIS-5).

### Aplicación

| Archivo | Caso de uso | Transacción y bloqueo |
|---|---|---|
| `backend/cimenta/presupuesto/aplicacion/historial_obra.py` (nuevo) | Puerto `FuenteHistorialObra` (`Protocol`: `nombre` y `contar(sesion_bd, obra_id) -> int`) y `contar_historial(sesion_bd, contexto, obra_id) -> ConteosHistorial`, que suma el conteo propio del repositorio y el de cada fuente inyectada | Corre dentro de la transacción del llamador, **después** del `FOR UPDATE` de la obra |
| `backend/cimenta/presupuesto/aplicacion/contexto.py` (cambio) | `ContextoPresupuesto.fuentes_historial: tuple[FuenteHistorialObra, ...] = ()` y el parámetro correspondiente en `construir_contexto` | — |
| `backend/cimenta/presupuesto/aplicacion/mantenimiento_obras.py` (nuevo) | `actualizar_obra(contexto, obra_id, cambios, usuario_id)` y `eliminar_obra(contexto, obra_id, usuario_id)` | Una transacción cada una. `SELECT … FOR UPDATE` de la obra; el estado y los valores se leen **después** de tomar el bloqueo |
| `backend/cimenta/presupuesto/aplicacion/ciclo_vida_obra.py` (nuevo) | `suspender_obra`, `reactivar_obra`, `cerrar_obra`, las tres sobre un único `_transicionar(operacion)` | Una transacción cada una. `FOR UPDATE` de la obra, `evaluar_transicion`, actualización del estado y asiento |

Detalle de cada caso de uso:

- **`actualizar_obra`.** Valida el rango de los porcentajes con `porcentajes_fuera_de_rango` (antes de abrir la transacción, como el alta); toma el bloqueo; si `not admite_edicion(estado)` lanza `ConflictoEstado(ESTADO_NO_PERMITE_OPERACION)` con el estado en el detalle (`CA-4`); calcula `cambios_efectivos`; si no hay ninguno responde con la obra tal como está y **no asienta** (`S-2`); si hay, actualiza solo esas columnas, fija `actualizado_en` y `actualizado_por_id`, y asienta `ACTUALIZAR` con `datos_antes` y `datos_despues` de los campos que cambiaron, `regla_negocio=None` (corregido tras la auditoría: `RN-25` es el IVA en el PRD y la edición no tiene `RN` propia) y `obra_id`. Un `umbral_alerta_pct: null` explícito borra el umbral.
- **`eliminar_obra`.** Toma el bloqueo; arma los conteos; si `hay_historial`, lanza `ConflictoEstado(OBRA_CON_HISTORIAL)` con detalle `{linea_base_congelada, lineas_base, importaciones, movimientos}` y las acciones que `operaciones_admitidas(estado)` permite (`SUSPENDER_OBRA`, `CERRAR_OBRA`; nunca una que respondería `409`); si no, asienta `ELIMINAR` con la fotografía de la obra en `datos_antes` (`codigo`, `nombre`, `estado`, parámetros), `regla_negocio="RN-01"`, y borra la fila. El asiento va **antes** del `DELETE` en la misma sesión; `bitacora.obra_id` no lleva clave foránea (modelo de datos §2), así que el asiento sobrevive a la obra. Un `DBAPIError` con `SQLSTATE` `23001` (otra tabla hija existe) se traduce **dentro del caso de uso**, antes de delegar en `traducir_error_del_motor`, a `OBRA_CON_HISTORIAL` con el nombre de la restricción en el detalle.
- **Transiciones.** `_transicionar` toma el bloqueo, llama a `evaluar_transicion`; si el dominio rechaza lanza `ConflictoEstado(ESTADO_NO_PERMITE_OPERACION)` con `{estado, operaciones_admitidas}` y las acciones correspondientes (rutas y métodos reales de la obra, filtrados por rol); si admite, escribe el estado, `actualizado_en` y `actualizado_por_id`, y asienta `SUSPENDER`, `REACTIVAR` o `CERRAR` con `datos_antes={"estado": …}`, `datos_despues={"estado": …}`, el `motivo` y `obra_id`. El `403` de rol y el `401` los resuelven las dependencias del enrutador, antes del caso de uso.

La lectura final (`obtener_obra`) del `Obra` de respuesta se hace en una transacción corta aparte, como en el alta.

### Infraestructura y esquema

| Objeto | Tipo | Detalle |
|---|---|---|
| `accion_bitacora` + `ELIMINAR` | migración | `ALTER TYPE accion_bitacora ADD VALUE 'ELIMINAR'`, sin `IF NOT EXISTS`, sin `BEFORE` ni `AFTER` (queda el vigésimo cuarto, tras `DAR_BAJA`) |
| `AccionBitacora.ELIMINAR` | enumerado de dominio de `auditoria` | Se añade en el mismo orden que el tipo; el docstring pasa de «23 verbos» a «24» |
| `repositorio_obra.bloquear_obra_completa(sesion, obra_id)` | consulta | `SELECT` de las columnas de la obra con `with_for_update()`; sin fila → `None` (el caso de uso lanza `NoEncontrado`) |
| `repositorio_obra.actualizar_obra(sesion, obra_id, campos, ahora, usuario_id)` | `UPDATE` | Solo las columnas de `campos`; los porcentajes cuantizados con `cuantizar().valor`, igual que el alta |
| `repositorio_obra.cambiar_estado_obra(sesion, obra_id, estado, ahora, usuario_id)` | `UPDATE` | Una sola sentencia con `WHERE id = :id`; el estado de origen ya lo validó el dominio bajo el bloqueo |
| `repositorio_obra.eliminar_obra(sesion, obra_id)` | `DELETE` | Una fila; el rol de aplicación ya tiene `DELETE` sobre `obra` (`0006`) |
| `repositorio_obra.contar_historial_propio(sesion, obra_id)` | consulta | Un solo `SELECT` con subconsultas escalares `count(*)` sobre `linea_base` (total y `CONGELADA`), `importacion`, `nivel`, `concepto`, `precio_insumo` y `rendimiento_observado`, todas filtradas por `obra_id`; aprovecha los índices por `obra_id` que existen en `linea_base`, `importacion`, `nivel` y `concepto`; `precio_insumo` y `rendimiento_observado` no tienen índice por `obra_id` y el conteo las recorre enteras (deuda declarada tras la auditoría, ver `impl.md`) |

**Migración:** `0017` (`v0017_auditoria_verbo_eliminar.py`) — reversible: sí · destructiva: la **bajada** sí lo es si hay asientos `ELIMINAR`, y por eso la guarda se niega · plan de reversa: la bajada bloquea `bitacora` con `ACCESS EXCLUSIVE`, se niega con `RAISE EXCEPTION` si existe algún asiento `ELIMINAR` (la bitácora es permanente, `RN-04`), y si no, renombra el tipo, crea otro con los 23 verbos de `0016` en su orden, convierte la columna con `USING accion::text::accion_bitacora` y borra el tipo antiguo. Con asientos `ELIMINAR`: respaldar con `pg_dump` y decidir con la persona dueña, igual que en `0016`. La subida no usa el valor nuevo (error `55P04` si lo hiciera en la misma ejecución de `upgrade head`). La bajada de `0017` debe ejecutarse **antes** que la de `0016` (lo impone el orden de Alembic). La revisión `0017` se reserva para este ticket: ver riesgo R-6 sobre el otro diseño en curso.

### API

Las cinco operaciones salen del borrador (`x-tickets: [TKT-012]`). El ticket **cambia el borrador** y el cambio pasa por el gate humano de este diseño:

- `x-tickets` de las cinco pasa a `[TKT-012b]`.
- `AccionBitacora` añade `ELIMINAR` al final (24 verbos).
- `reactivar_obra` pierde el `(asumido)` de su descripción: D-2 lo confirmó.
- `actualizar_obra` declara `additionalProperties: false` en `ObraCambios` y que un cuerpo con `codigo`, `tipo_contrato` o `estado` responde `422`; documenta el `409` `ESTADO_NO_PERMITE_OPERACION` por obra `CERRADA` y que `umbral_alerta_pct: null` borra el umbral.
- `eliminar_obra`: el `409` de ejemplo cambia a `OBRA_CON_HISTORIAL` con el detalle `{linea_base_congelada, lineas_base, importaciones, movimientos}` y declara que las acciones dependen del estado.
- Las tres transiciones declaran el `409` `ESTADO_NO_PERMITE_OPERACION` con `estado` y `operaciones_admitidas` en el detalle.
- `CodigoConflicto` **no cambia**: `OBRA_CON_HISTORIAL` y `ESTADO_NO_PERMITE_OPERACION` ya están en el catálogo cerrado.

| `operationId` · método y ruta | DTO entrada | DTO salida | Códigos y `tipo` de error | `x-roles` |
|---|---|---|---|---|
| `actualizar_obra` · `PATCH /api/v1/obras/{obra_id}` | `ObraCambios` (nuevo, `extra="forbid"`) | `Obra` | `200` · `409 CONFLICTO ESTADO_NO_PERMITE_OPERACION` · `404 NO_ENCONTRADO` · `422 VALIDACION` · `403` · `401` | `DIRECTOR_PROYECTOS`, `DIRECCION_GENERAL` |
| `eliminar_obra` · `DELETE /api/v1/obras/{obra_id}` | — | — (`204`) | `204` · `409 CONFLICTO OBRA_CON_HISTORIAL` · `404` · `403` · `401` | ídem |
| `suspender_obra` · `POST /api/v1/obras/{obra_id}/suspension` | `Motivo` | `Obra` | `200` · `409 CONFLICTO ESTADO_NO_PERMITE_OPERACION` · `404` · `422` · `403` · `401` | ídem |
| `reactivar_obra` · `POST /api/v1/obras/{obra_id}/reactivacion` | `Motivo` | `Obra` | ídem | ídem |
| `cerrar_obra` · `POST /api/v1/obras/{obra_id}/cierre` | `Motivo` | `Obra` | ídem | ídem |

Todas las rutas se declaran `def`, llevan `verificar_origen` (CSRF) y `exigir_rol(*ROLES_ALTA)`, y devuelven un `Obra` construido con `Obra.desde(...)` tras releer. `DELETE` responde `204` sin cuerpo y no lleva `response_model`.

`ObraCambios` reutiliza los tipos `NombreObra`, `DomicilioObra` y `PorcentajeEntrada` de `ObraNueva` (mismas longitudes y rechazo de `NUL`), todos opcionales; `iva_acreditable` es `StrictBool`. Distingue ausente de `null` con `model_fields_set` (solo `umbral_alerta_pct` admite `null`; `nombre: null` es `422`). Un modelo validador exige al menos un campo (`cuerpo vacío` → `422`). Con `ConfigDict(extra="forbid")`, Pydantic emite `extra_forbidden` para `codigo`, `tipo_contrato` y `estado`, y el manejador global lo lleva a `422` `VALIDACION` señalando el campo (confirmado en la documentación de Pydantic 2.12 vía Context7; el mapeo al contrato de error se comprueba en la fila A7, `(sin ejecutar)`).

### Frontend

| Componente o vista | Datos | Estados |
|---|---|---|
| `PantallaObras.tsx` (cambio): columna «Acciones» por fila, formulario de edición, motivo y confirmación | `obrasOptions` existente; mutaciones nuevas en `obras.consultas.ts`; la lista se invalida con `claves.obras` tras cada operación | cargando · vacío · error · **bloqueado** (`OBRA_CON_HISTORIAL` y `ESTADO_NO_PERMITE_OPERACION` en `ConflictoEnLinea`) |
| `obras.acciones.ts` (nuevo) | `accionesDeFila(estado, roles)` | — (función pura) |
| `obras.formulario.ts` (cambio) | `esquemaEdicionObra`, `CAMPOS_EDICION_OBRA`, `valoresDeEdicion(obra)` | errores de campo del `422` junto al campo |
| `FormularioCatalogo.tsx` (cambio aditivo) | campo con `soloLectura: true` | sin cambio de estados |
| `dinero.ts` (cambio aditivo) | `fraccionAPorcentaje(fraccion)` | — |

Reglas de la pantalla:

- **Acciones por fila** (`CA-14`, ver D-DIS-1): `PLANEACION` → Editar, Eliminar, Cerrar; `ACTIVA` → Editar, Suspender, Cerrar; `SUSPENDIDA` → Editar, Reactivar, Cerrar; `CERRADA` → ninguna; roles sin escritura → ninguna. Es cortesía de navegación: el servidor sigue respondiendo `403` y `409`.
- **Editar** abre `FormularioCatalogo` con `esquemaEdicionObra` (nombre, domicilio, los dos porcentajes, umbral e IVA editables; código y tipo de contrato como campos de solo lectura). El `alGuardar` envía solo los campos editables; el `422` cae junto al campo por la misma vía que el alta. No hay control de concurrencia optimista: gana la última escritura (supuesto 4 de la pasada de la spec).
- **Suspender, Reactivar y Cerrar** abren `CapturaMotivo`; sin motivo no se envía y el campo señala el error (`CA-17`). El `409` `ESTADO_NO_PERMITE_OPERACION` se pinta en línea con su estado actual, y al cerrar el diálogo la lista se refresca para mostrar el estado real.
- **Eliminar** abre `ConfirmacionBaja` con el código de la obra en la pregunta (Should de la spec). El `409` `OBRA_CON_HISTORIAL` se pinta con `ConflictoEnLinea`: mensaje, detalle y **las acciones del contrato** (`BotonesAcciones`). Al pulsar una acción cuyo `clave` es `SUSPENDER_OBRA` o `CERRAR_OBRA`, la pantalla abre `CapturaMotivo` y envía con la función tipada correspondiente sobre la obra de esa fila; una clave desconocida no se pinta como botón. El contrato decide **cuáles** se ofrecen; el cliente solo sabe cómo ejecutar las claves que el borrador declara.

## Orden de implementación

Se ejecuta fila por fila con el ciclo TDD de [metodología §16](../../metodologia.md#16--el-ciclo-tdd). La verificación de cada fila corre **antes** de pasar a la siguiente. Los tests de una fila los escribe `tester-backend`, `tester-api` o `tester-frontend` en rojo antes del código. Estimación en líneas incluyendo pruebas; ninguna fila pasa de unas 400.

### Entrega a · backend (filas A1 a A9)

| # | Paso | Tests que pone en verde | Agente | Modelo | Verificación | Estado |
|---|---|---|---|---|---|---|
| A1 | Migración `0017` con `ELIMINAR`, `AccionBitacora.ELIMINAR` y la sonda de `55P04`. Actualiza `MENSAJE_ACCION` y el docstring de `auditoria/dominio/asiento.py` (de 23 a 24 verbos) y las siete aserciones con «23» fijo que la subida pone en rojo: `test_tkt007_dominio.py:434`, `test_tkt007_fronteras.py:247`, `test_tkt007_esquema.py:262`, `:268` y `:543`, `test_tkt029b_migracion.py:270` (TC-02, que compara la base en `head` con los verbos de `0016`) y `test_tkt029b_api_baja.py:1414` (`verbos[-1] == "DAR_BAJA"`); es una ampliación declarada, con el mismo patrón que cuando `0016` pasó de 22 a 23. Escribe el ADR del verbo (ver «¿Merece ADR?») y lo añade a `docs/adr/README.md`. ~260 líneas | TC-01 a TC-04, TC-INV-1 | `desarrollador-sql` | `sonnet` · disparador: reescribe `bitacora` (tabla de solo anexado) con una guarda de permanencia, el mismo molde que `0016`, cuyas pruebas ya demostraron el riesgo | `alembic upgrade head`, `downgrade -1`, `upgrade head`; `pytest tests/test_tkt012b_migracion.py`; `auditor-sql` sin hallazgos de reversibilidad | ✓ Hecho |
| A2 | Dominio: `ciclo_vida_obra.py` y `historial_obra.py`. ~220 líneas | TC-05 a TC-13 | `desarrollador-dominio` | `haiku` | `pytest tests/test_tkt012b_dominio_*.py`; `uv run python -m herramientas.verificar_float`; `uv run lint-imports` | ✓ Hecho |
| A3 | Repositorio de la obra: las cinco funciones nuevas. ~230 líneas | TC-14 a TC-18 | `desarrollador-sql` | `sonnet` · disparador: bloqueo pesimista (`FOR UPDATE`) y una consulta multitabla | `pytest tests/test_tkt012b_repositorio_obra.py` con PostgreSQL real y el rol de aplicación; `mypy` | ✓ Hecho |
| A4 | Puerto `FuenteHistorialObra`, `contar_historial` y el campo del contexto. El contexto se construye en `presupuesto/api/montaje.py` y no en `servidor/`, así que `montar_presupuesto` y `construir_contexto` reciben un parámetro nuevo `fuentes_historial` (por omisión `()`); `servidor/fabrica.py` no pasa nada hoy y es quien lo hará cuando un módulo publique su fuente (D-DIS-7). Escribe el ADR del puerto. ~150 líneas | TC-19, TC-20 | `desarrollador-aplicacion` | `haiku` | `pytest tests/test_tkt012b_historial.py`; `lint-imports` (no aparece `compras` en `presupuesto`) | ✓ Hecho |
| A5 | Casos de uso `actualizar_obra` y `eliminar_obra`. ~300 líneas | TC-21 a TC-32 | `desarrollador-aplicacion` | `sonnet` · disparador: bloqueo pesimista, carrera con el congelado y asiento en la misma transacción | `pytest tests/test_tkt012b_mantenimiento_obras.py`; `mypy` | ✓ Hecho |
| A6 | Casos de uso de las tres transiciones. ~220 líneas | TC-33 a TC-40 | `desarrollador-aplicacion` | `sonnet` · disparador: serialización de dos transiciones con la fila bloqueada | `pytest tests/test_tkt012b_ciclo_vida_obra.py` | ✓ Hecho |
| A7 | API: `ObraCambios` y las cinco rutas, cableadas a los casos de uso. Ampliaciones declaradas de pruebas existentes: `CUERPOS_VALIDOS` de `test_tkt057_csrf.py:1265-1327` (una entrada por cada ruta que muta, con el patrón de `:1323-1326`) e `IMPLEMENTADAS_DE_PRESUPUESTO` de `test_tkt017_api_congelado.py:128-139`, cuyo filtro `"TKT-012" in x-tickets` (`:1107`) no reconoce `[TKT-012b]` y dejaría vacío el conjunto esperado: se amplía el filtro a `TKT-012b` y el borrador conserva `x-tickets: [TKT-012b]` (D-DIS-7). ~340 líneas | TC-41 a TC-52 | `desarrollador-api` | `haiku` | `pytest tests/test_tkt012b_api_obras.py` con cliente HTTP real, sesión y CSRF; `mypy`; `ruff check` | ✓ Hecho |
| A8 | Borrador OpenAPI y tipos del cliente (`npm run tipos:generar`). ~120 líneas | TC-53, TC-54 | `desarrollador-api` | `haiku` | `python tools/verificar_docs.py`; `npm run tipos:verificar`; el contrato de `/openapi.json` coincide con el borrador | ✓ Hecho |
| A9 | Cierre de la entrega a: pruebas de concurrencia (carrera con el congelado, dos transiciones, borrado frente a una escritura que cuelga de la obra), regresión y mutación. Solo tests. ~250 líneas | TC-55 a TC-62, TC-INV-2 a TC-INV-5 | `tester-backend` | `sonnet` · disparador: concurrencia | `uv run pytest` completo en verde; la tabla «mutante · test que cae» de `impl.md` | ⚠ Ajustado: el verde corrigió un defecto de producción que A9 destapó (`55P03` sin traducir) |

### Entrega b · pantalla y prueba de extremo a extremo (filas B1 a B6)

| # | Paso | Tests que pone en verde | Agente | Modelo | Verificación | Estado |
|---|---|---|---|---|---|---|
| B1 | `fraccionAPorcentaje` en `dinero.ts` y `soloLectura` en `FormularioCatalogo`. ~140 líneas | TC-63, TC-64, TC-INV-6 | `desarrollador-react` | `haiku` | `npm test`; las pruebas existentes de `FormularioCatalogo` pasan sin tocarse | ✓ Hecho |
| B2 | `obras.consultas.ts` (cinco mutaciones tipadas), `obras.acciones.ts` y `obras.formulario.ts` de edición. ~200 líneas | TC-65 a TC-68 | `desarrollador-react` | `haiku` | `npm test`; `npm run typecheck`; `npm run lint` | ✓ Hecho |
| B3 | `PantallaObras`: columna «Acciones» y formulario de edición. La columna (encabezado y celdas) solo se dibuja si el rol puede operar; `PantallaObras.test.tsx:529` exige para los lectores exactamente `Código`, `Nombre` y `Estado`. ~250 líneas | TC-69 a TC-72 | `desarrollador-react` | `haiku` | `npm test` (archivo nuevo, no el de TKT-012a); `typecheck` | ✓ Hecho |
| B4 | `PantallaObras`: motivo (suspender, reactivar, cerrar), confirmación de eliminar y bloqueo `OBRA_CON_HISTORIAL` con sus acciones del contrato. Añade los rótulos «Suspender» y «Cerrar» a `ETIQUETAS_ACCION` de `compartido/componentes/bloqueo/etiquetas.ts:122-134`: sin ellos `BotonesAcciones` pintaría la clave cruda. ~320 líneas | TC-73 a TC-79 | `desarrollador-react` | `haiku` | `npm test`; el bloqueo muestra las acciones que trae el mock del contrato, no unas cableadas | ⚠ Ajustado: se añadió TC-73b (409 de estado dentro del diálogo de motivo) |
| B5 | Semilla de humo: `semilla_linea_base_local` admite congelar la línea base importando `congelar` de `presupuesto/aplicacion/congelado.py`, como ya hace `herramientas/soporte_tkt017_entorno.py` (`congelar_linea_base` no está en `presupuesto/interfaz.py` y `herramientas/` queda fuera de `import-linter`; no se amplía la interfaz publicada); `preparacion-global.ts` siembra dos obras de mantenimiento. ~150 líneas | TC-80 | `desarrollador-sql` | `haiku` | `uv run --env-file ../.env python -m herramientas.semilla_linea_base_local` con la opción de congelar devuelve una obra `ACTIVA`; `pytest` de la herramienta | ✓ Hecho |
| B6 | Prueba E2E `CA-18` en `frontend/e2e/obras.spec.ts` y actualización del wireframe «Obras». ~180 líneas | TC-81 | `desarrollador-react` | `haiku` | `npm run e2e` con Docker en marcha | ✓ Hecho |

**Modelo:** `haiku` por omisión; `sonnet` solo con el disparador citado de [metodología §14](../../metodologia.md#14--enrutamiento-de-modelo). Nunca `opus` en una fila de ejecución.

**Antes de construir encima, la fila A1 comprueba tres supuestos `(sin ejecutar)`** que este diseño da por ciertos: (1) que `ALTER TYPE … ADD VALUE 'ELIMINAR'` seguido de un `INSERT` del valor en la misma transacción falla con `55P04`, igual que con `DAR_BAJA`; (2) que `SELECT … FOR UPDATE` sobre la fila de `obra` bloquea el `INSERT` de una fila hija que apunta a ella (`FOR KEY SHARE` choca con `FOR UPDATE`), que es lo que hace segura la carrera de borrado contra otro módulo; (3) que un `DELETE FROM obra` con una fila hija responde `23001` (`restrict_violation`) y no `23503`. El comando es la propia sonda de A1 y A3 con PostgreSQL de testcontainers, ejecutada por `tester-backend`; si alguna falla, la fila se detiene y se escala.

## Plan de pruebas

Los nombres siguen la convención `test_hdu001_esc20_…` y `test_tkt012b_ca<N>_…`. Cada rechazo comprueba el contrato de error completo: `tipo`, `codigo`, `mensaje`, `detalle` y `acciones`.

| # | Caso | Tipo | Criterio que cubre | Escenario |
|---|---|---|---|---|
| TC-01 | La subida añade `ELIMINAR` al final de `accion_bitacora` y `AccionBitacora` coincide con el tipo | feliz | `CA-5` | HDU-001 esc. 20 |
| TC-02 | Sonda: usar `ELIMINAR` en la misma transacción que lo añade falla con `55P04` (supuesto 1) | rechazo | `CA-5` | — |
| TC-03 | La bajada, sin asientos `ELIMINAR`, deja el tipo con los 23 verbos de `0016` y conserva filas y privilegios de `bitacora` | regresión | `CA-R3` | — |
| TC-04 | La bajada **se niega** con asientos `ELIMINAR` y no pierde ninguno | **rechazo** | `CA-5` | — |
| TC-05 | `evaluar_transicion`: las cuatro transiciones admitidas de D-2 | feliz | `CA-8` | HDU-001 esc. 20 |
| TC-06 | `evaluar_transicion`: `PLANEACION → CERRADA` admitida | feliz | `CA-8` (ejemplo añadido) | — |
| TC-07 | `evaluar_transicion`: las siete combinaciones prohibidas de `CA-9` rechazan con estado actual y operaciones admitidas | **rechazo** | `CA-9` | — |
| TC-08 | `admite_edicion`: solo `CERRADA` es falso | **rechazo** | `CA-4` | — |
| TC-09 | `cambios_efectivos`: un valor igual al actual no cuenta; el antes y el después solo traen los campos cambiados | feliz | `CA-1` | — |
| TC-10 | `cambios_efectivos`: sin cambios reales devuelve vacío | feliz | `CA-1` variante | — |
| TC-11 | `cambios_efectivos`: `umbral_alerta_pct` a `None` borra el umbral; ausente lo conserva | feliz | `CA-1` variante | — |
| TC-12 | `hay_historial`: verdadero con cada fuente por separado (línea base, importación, filas propias, movimientos externos) y falso con todo en cero | feliz y **rechazo** | `CA-5`, `CA-6` | HDU-001 esc. 20 |
| TC-13 | `ciclo_vida_obra.py` y `historial_obra.py` no importan nada fuera de la biblioteca estándar y `tipos_base`, y no usan `float` | regresión | — | — |
| TC-14 | `bloquear_obra_completa` toma `FOR UPDATE`: una segunda sesión espera hasta que la primera confirma | concurrencia | `CA-13` | — |
| TC-15 | `actualizar_obra` y `cambiar_estado_obra` escriben solo lo indicado y fijan `actualizado_en` y `actualizado_por_id` | feliz | `CA-1`, `CA-8` | — |
| TC-16 | `eliminar_obra` borra la fila y libera `uq_obra_codigo`; con una línea base hija responde `23001` | **rechazo** | `CA-5`, `CA-R3` | HDU-001 esc. 20 |
| TC-17 | `contar_historial_propio` cuenta cada tabla por separado y con la línea base congelada marcada | feliz | `CA-6` | — |
| TC-18 | Las restricciones de `0006` (`uq_obra_codigo`, los dos `CHECK` de rango, `ck_obra_umbral_alerta_pct_no_negativo`, `ck_obra_estado`) siguen rechazando por SQL directo | regresión | `CA-R3` | — |
| TC-19 | `contar_historial` suma las fuentes inyectadas y la propia; sin fuentes, `movimientos` es cero | feliz | `CA-6` | — |
| TC-20 | Una fuente que lanza una excepción **propaga** el fallo y no deja pasar el borrado | **rechazo** | `CA-6` | — |
| TC-21 | `actualizar_obra` cambia nombre y porcentaje, deja código, tipo y estado, y asienta `ACTUALIZAR` con antes y después en la misma transacción | feliz | `CA-1` | HDU-001 |
| TC-22 | `actualizar_obra` por Dirección General, y sobre una obra `SUSPENDIDA` (que sí se edita, D-3) | feliz | `CA-1` variante | — |
| TC-23 | `actualizar_obra` con `umbral_alerta_pct: null` borra el umbral y asienta | feliz | `CA-1` variante | — |
| TC-24 | `actualizar_obra` sin cambios reales responde la obra y **no** asienta | feliz | `CA-1` variante | — |
| TC-25 | `actualizar_obra` con la obra `CERRADA` → `409` `ESTADO_NO_PERMITE_OPERACION` con el estado; obra y bitácora intactas | **rechazo** | `CA-4` | — |
| TC-26 | `actualizar_obra` con porcentaje fuera de rango → `422`; ni cambio ni asiento | **rechazo** | `CA-3` | — |
| TC-27 | `actualizar_obra` con un fallo del asiento deshace el cambio (misma transacción) | **rechazo** | `CA-1` | regla 8 |
| TC-28 | `eliminar_obra` sin historial: la obra desaparece, el código queda libre y el asiento `ELIMINAR` conserva código y nombre | feliz | `CA-5` | HDU-001 esc. 20 |
| TC-29 | `eliminar_obra` con línea base congelada → `409 OBRA_CON_HISTORIAL`, `linea_base_congelada` verdadero, acciones `SUSPENDER_OBRA` y `CERRAR_OBRA` con método y ruta, nada se borra y no hay asiento | **rechazo** | `CA-6` | HDU-001 esc. 20 |
| TC-30 | `eliminar_obra` con solo una importación (sin línea base congelada) → mismo `409` con `linea_base_congelada` falso | **rechazo** | `CA-6` ejemplo 2 | — |
| TC-31 | `eliminar_obra` con la obra en `PLANEACION` y con historial: las acciones son **solo** `CERRAR_OBRA` (objeción 5 de la spec); con la obra `CERRADA` las acciones son `[]` | **rechazo** | `CA-6`, `CA-9` | — |
| TC-32 | `eliminar_obra` con una fila de otro módulo que cuelga de la obra (`requisicion` insertada por SQL) y sin fuente inyectada → `23001` traducido a `409 OBRA_CON_HISTORIAL` | **rechazo** | `CA-6` | — |
| TC-33 | Cada transición admitida cambia el estado y asienta `SUSPENDER`, `REACTIVAR` o `CERRAR` con estado anterior, estado nuevo y motivo | feliz | `CA-8` | HDU-001 esc. 20 |
| TC-34 | Dirección General puede igual | feliz | `CA-8` variante | — |
| TC-35 | Las siete combinaciones no admitidas → `409 ESTADO_NO_PERMITE_OPERACION` con `estado` y `operaciones_admitidas`; obra y bitácora intactas | **rechazo** | `CA-9` | — |
| TC-36 | Motivo ausente, vacío, de solo espacios, de más de 2000 caracteres o con `NUL` → `422` señalando `motivo` | **rechazo** | `CA-10` | — |
| TC-37 | `PLANEACION → CERRADA` con motivo asienta `CERRAR` | feliz | `CA-8` (ejemplo añadido) | — |
| TC-38 | Las transiciones no tocan ningún dato histórico de la obra (línea base y control quedan idénticos) | regresión | `CA-8`, `CA-R4` | — |
| TC-39 | El estado leído tras el bloqueo es el vigente: una transición que esperó el `FOR UPDATE` se evalúa contra el estado nuevo | concurrencia | `CA-13` | — |
| TC-40 | Un fallo del asiento deshace la transición | **rechazo** | `CA-8` | regla 8 |
| TC-41 | `PATCH` feliz: `200`, cuerpo `Obra`, porcentajes como cadena | feliz | `CA-1` | — |
| TC-42 | `PATCH` con `codigo`, `tipo_contrato` o `estado` → `422 VALIDACION` señalando el campo; sin cambios ni asiento | **rechazo** | `CA-2` | — |
| TC-43 | `PATCH` con cuerpo vacío → `422` | **rechazo** | `CA-2` | — |
| TC-44 | `PATCH` con nombre vacío, domicilio vacío, porcentaje fuera de rango o con más de 6 decimales, `iva_acreditable` no booleano (`"yes"`, `1`) o texto con `NUL` → `422` por campo | **rechazo** | `CA-3` | — |
| TC-45 | `PATCH` con `nombre: null` → `422`; `umbral_alerta_pct: null` → `200` | **rechazo** y feliz | `CA-3`, `CA-1` | — |
| TC-46 | `DELETE` feliz → `204` sin cuerpo; la lista ya no lo trae | feliz | `CA-5` | HDU-001 esc. 20 |
| TC-47 | `DELETE` con historial → `409` con el contrato completo, y las acciones en el cuerpo son las rutas reales de esa obra | **rechazo** | `CA-6` | — |
| TC-48 | Las tres transiciones por HTTP: `200` y `409` | feliz y **rechazo** | `CA-8`, `CA-9` | — |
| TC-49 | Sin sesión → `401` en las cinco operaciones; obra y bitácora intactas | **rechazo** | `CA-11` | — |
| TC-50 | Compras, Almacén, Residente y Administración → `403` `PERMISO` sin cifras en las cinco | **rechazo** | `CA-11` | — |
| TC-51 | Sin cabecera CSRF → `403` en las cinco | **rechazo** | `CA-11` | — |
| TC-52 | `obra_id` inexistente → `404` `NO_ENCONTRADO` en las cinco; sin asiento. Y un `obra_id` que no es UUID → `422` | **rechazo** | `CA-12` | — |
| TC-53 | Las cinco operaciones del borrador coinciden con las rutas publicadas por `/openapi.json` (método, ruta, códigos, `x-tickets`) | regresión | DoD | — |
| TC-54 | Los tipos generados del cliente difieren de los versionados si el borrador cambia | regresión | DoD | — |
| TC-55 | **Concurrencia:** borrado y congelado a la vez sobre una obra en `PLANEACION` con línea base `BORRADOR` materializada; en todas las corridas el congelado gana, el borrado responde `409 OBRA_CON_HISTORIAL`, no queda línea base `CONGELADA` sin obra y ninguna responde `500` | concurrencia | `CA-7`, `CA-R4` | — |
| TC-56 | **Concurrencia:** borrado de una obra sin historial a la vez que una escritura de otro módulo que cuelga de ella (`requisicion` por SQL): exactamente una gana; si gana la escritura, el borrado responde `409`; si gana el borrado, la escritura falla con una violación de clave foránea, nunca con un `500` del servidor de este ticket | concurrencia | `CA-7` | — |
| TC-57 | **Concurrencia:** suspensión y cierre a la vez sobre una obra `ACTIVA`: resultado final coherente (`CERRADA`, o `SUSPENDIDA` y después `CERRADA`), cada ganadora con su asiento y ninguna `500` | concurrencia | `CA-13` | — |
| TC-58 | **Concurrencia:** dos suspensiones a la vez: una `200` y la otra `409` | concurrencia | `CA-13` | — |
| TC-59 | **Concurrencia:** edición y cierre a la vez: la edición que pierde la carrera responde `409` (`CERRADA`) y no escribe | concurrencia | `CA-4`, `CA-13` | — |
| TC-60 | Con `lock_timeout` agotado, el `55P03` se traduce a `409 CONCURRENCIA` con la acción `REINTENTAR` | **rechazo** | `CA-13` | — |
| TC-61 | Borrar una obra sin historial no altera filas de líneas base congeladas de **otras** obras ni deja huérfanos | regresión | `CA-R4` | — |
| TC-62 | El disparador de inmutabilidad de la línea base sigue rechazando `UPDATE` y `DELETE` sobre copias congeladas | regresión | `CA-R4` | invariante 14 |
| TC-INV-1 | La subida y la bajada de `0017` conservan el esquema de `0016` | regresión de invariante | `CA-R3` | — |
| TC-INV-2 | El congelado de una obra `PLANEACION` sigue pasándola a `ACTIVA` con la máquina de estados nueva en el código | regresión de invariante | `CA-R1` | `PA-T17.8` |
| TC-INV-3 | El congelado de una obra `CERRADA` o `SUSPENDIDA` se rechaza como hoy (`ESTADO_NO_PERMITE_OPERACION`) | regresión de invariante | `CA-R1` | — |
| TC-INV-4 | La suite de TKT-012a (alta, lista, consulta, `CODIGO_OBRA_DUPLICADO`) pasa sin tocarse; `GET` sigue abierto a los seis roles | regresión de invariante | `CA-R2` | — |
| TC-INV-5 | Un alta con un código recién liberado por un borrado funciona | regresión de invariante | `CA-5` | — |
| TC-63 | `fraccionAPorcentaje`: `"0.150000"` → `"15"`, `"0.055000"` → `"5.5"`, `"0"` → `"0"`, `"1"` → `"100"`; ida y vuelta con `porcentajeAFraccion` sin `Number` | feliz | `CA-15` | — |
| TC-64 | Un campo `soloLectura` se muestra con su valor, no se puede editar y no viaja al `alGuardar` | feliz | `CA-15` | — |
| TC-INV-6 | Las pruebas de `FormularioCatalogo`, `CapturaMotivo`, `ConfirmacionBaja` y `ConflictoEnLinea` no cambian y siguen en verde | regresión de invariante | `CA-R5` | — |
| TC-65 | `accionesDeFila` devuelve las listas de `CA-14` para cada estado y rol (incluido `PLANEACION` con Cerrar) | feliz | `CA-14` | — |
| TC-66 | `accionesDeFila` devuelve `[]` para Compras, Almacén, Residente y Administración con cualquier estado | **rechazo** | `CA-14` | — |
| TC-67 | Las mutaciones envían método, ruta y cuerpo del contrato; una sin motivo no sale | feliz | `CA-17` | — |
| TC-68 | `esquemaEdicionObra` no incluye `codigo`, `tipo_contrato` ni `estado` | **rechazo** | `CA-2`, `CA-15` | — |
| TC-69 | La fila ofrece las acciones de `CA-14` según estado y rol | feliz | `CA-14` | — |
| TC-70 | Editar: el formulario se abre con los valores de la obra, el código y el tipo de solo lectura; al guardar la lista muestra el nombre nuevo sin recargar | feliz | `CA-15` | — |
| TC-71 | Editar: un `422` se pinta junto al campo, no en una pantalla aparte | **rechazo** | `CA-15` | — |
| TC-72 | Editar con la obra `CERRADA` (otra pestaña la cerró): el `409` se pinta en línea con el estado | **rechazo** | `CA-4` | — |
| TC-73 | Suspender con motivo: la fila pasa a «Suspendida» y ofrece «Reactivar» | feliz | `CA-17` | — |
| TC-74 | Suspender sin motivo: el botón de confirmar no envía y el campo señala el error | **rechazo** | `CA-17` | — |
| TC-75 | Reactivar y Cerrar con motivo; tras cerrar, la fila no ofrece acciones | feliz | `CA-14`, `CA-17` | — |
| TC-76 | Eliminar sin historial: confirma con el código en la pregunta y la obra sale de la lista | feliz | `CA-5` | — |
| TC-77 | Eliminar con historial: se pinta el bloqueo con el mensaje y el detalle del servidor; ofrece solo las acciones que trae el contrato; la obra sigue en la lista | **rechazo** | `CA-16` | HDU-001 esc. 20 |
| TC-78 | Las acciones del bloqueo no son cableadas: con un mock que devuelve solo `CERRAR_OBRA`, solo se ofrece «Cerrar» | **rechazo** | `CA-16` | — |
| TC-79 | Cancelar la confirmación o el motivo no envía nada | **rechazo** | `CA-17` | — |
| TC-80 | La semilla con la opción de congelar entrega una obra `ACTIVA` con línea base congelada; sin la opción, `PLANEACION` con `BORRADOR` (como hoy) | feliz | `CA-18` | — |
| TC-81 | **E2E** `CA-18`: editar el nombre, suspender, reactivar y listar (obra M1, `ACTIVA`); intentar eliminar la obra con historial (obra M2, `PLANEACION` con línea base `BORRADOR`) y ver `OBRA_CON_HISTORIAL` | feliz y **rechazo** | `CA-18` | HDU-001 esc. 20 |

### Mutación

Rutas críticas de este ticket: la decisión de historial, la máquina de estados y el orden del bloqueo. Mutantes a probar en A9 (y los que surjan van a la tabla «mutante · test que cae» de `impl.md`):

| Mutante | Test que debe ponerse rojo |
|---|---|
| `hay_historial` ignora `importacion` | TC-12, TC-30 |
| `hay_historial` ignora la línea base `BORRADOR` | TC-12, TC-55 |
| `hay_historial` ignora los movimientos de las fuentes inyectadas | TC-12, TC-19 |
| `evaluar_transicion` admite `CERRADA → CERRADA` o `PLANEACION → SUSPENDIDA` | TC-07, TC-35 |
| `evaluar_transicion` rechaza `PLANEACION → CERRADA` | TC-06, TC-37 |
| `admite_edicion` bloquea también `SUSPENDIDA` | TC-08, TC-22 y la variante de edición con obra suspendida |
| El caso de uso lee el estado **antes** del `FOR UPDATE` | TC-39, TC-57, TC-59 |
| El `DELETE` se ejecuta antes del conteo de historial | TC-29, TC-55 |
| El asiento se escribe fuera de la transacción del cambio | TC-27, TC-40 |
| `cambios_efectivos` asienta aunque no cambie nada | TC-24 |
| `eliminar_obra` omite el asiento `ELIMINAR` | TC-28 |
| La acción `SUSPENDER_OBRA` se ofrece desde `PLANEACION` | TC-31 |
| La guarda de la bajada de `0017` no se niega con asientos | TC-04 |

## Entradas hostiles y datos inesperados

| Campo | Qué se rechaza | Código | Test |
|---|---|---|---|
| `nombre`, `domicilio` (`PATCH`) | Vacío, de solo espacios, `null`, con `NUL` (`psycopg` lo rechaza y daría `500`), más largo que el tope que ya fija `ObraNueva` | `422` `VALIDACION` | TC-44, TC-45 |
| `retencion_destajo_pct`, `fondo_garantia_pct`, `umbral_alerta_pct` | Fuera de 0 a 1 (el umbral, negativo), más de 6 decimales, dígitos no ASCII, salto de línea final, número JSON en lugar de cadena | `422` `VALIDACION` (forma) o `FUERA_DE_RANGO` | TC-26, TC-44 |
| `iva_acreditable` | Cualquier cosa que no sea un booleano JSON (`"yes"`, `1`, `"true"`): `StrictBool` | `422` | TC-44 |
| `codigo`, `tipo_contrato`, `estado` | Presentes en el cuerpo del `PATCH` | `422` | TC-42 |
| Cuerpo | `{}`, `null`, una lista, campos desconocidos | `422` | TC-43 |
| `motivo` (tres transiciones) | Ausente, vacío, de solo espacios, de más de 2000 caracteres, con `NUL` | `422` | TC-36 |
| `obra_id` (ruta) | No es un UUID | `422` | TC-52 |

## Impacto

Resultado de `revisor-impacto` (2026-11-17): veredicto inicial «diseño incompleto», con once hallazgos (tres altos, tres medios, cinco bajos), todos incorporados arriba. Verificó con comandos que `lint-imports` pasa hoy (16 contratos, 0 rotos), que las claves foráneas `ON DELETE RESTRICT` hacia `obra` son las que el diseño cuenta, que `bitacora.obra_id` y `archivo.obra_id` no tienen clave foránea, que el rol de aplicación tiene `DELETE` sobre `obra`, que `extra_forbidden` llega como `422` `VALIDACION` por `manejadores.py` y que la revisión `0017` está libre en todas las ramas.

| Qué se toca | Quién depende | Riesgo | Mitigación |
|---|---|---|---|
| `AccionBitacora` y el tipo `accion_bitacora` | `auditoria` (valida el verbo antes de insertar; `MENSAJE_ACCION`), la consulta de bitácora, el borrador y siete aserciones con «23» fijo en `test_tkt007_*` y `test_tkt029b_*` | Esas siete aserciones se ponen en rojo al subir a 24 verbos. El frontend hoy no consume `AccionBitacora` | A1 las actualiza como ampliación declarada; A8 regenera los tipos y `tipos:verificar` falla si difieren |
| `CUERPOS_VALIDOS` (`test_tkt057_csrf.py`) e `IMPLEMENTADAS_DE_PRESUPUESTO` (`test_tkt017_api_congelado.py`) | Las pruebas de CSRF y de conformidad del enrutador con el borrador | Las cinco rutas nuevas ponen ambas en rojo | A7 las amplía (D-DIS-7) |
| `etiquetas.ts` (`ETIQUETAS_ACCION`) y `PantallaObras.test.tsx:529` | Todas las pantallas con bloqueo; la prueba que fija las columnas de los lectores | Rótulos crudos en el bloqueo; una columna «Acciones» incondicional rompería la prueba de 012a | B4 añade los rótulos; B3 dibuja la columna solo para quien puede operar |
| `ContextoPresupuesto` (campo nuevo con valor por omisión) | `montar_presupuesto`, `semilla_linea_base_local` (construye el contexto a mano) y las pruebas que lo construyen | Un constructor posicional se rompería | El campo va al final con `= ()`; ninguna firma existente cambia |
| `repositorio_obra.py` | Alta, lista y consulta de TKT-012a | Una consulta nueva podría cambiar el orden o las columnas de las existentes | Solo se añaden funciones; `TC-INV-4` ejecuta la suite de 012a sin tocarla |
| Fila `obra` (borrado físico) | Cualquier tabla con `obra_id` y `ON DELETE RESTRICT`; `bitacora.obra_id` (sin clave foránea); `archivo.obra_id` (sin clave foránea, hoy sin consumidores) | Un archivo o asiento que apunte a una obra que ya no existe | Los asientos de bitácora sobreviven por diseño. `archivo` aún no tiene escritores; su fuente de historial entra con su ticket (R-2) |
| Congelado (`congelado.py`, `repositorio_linea_base.activar_obra`) | La arista `PLANEACION → ACTIVA` | Que la máquina nueva la modele distinto | No se toca; `TC-INV-2` y `TC-INV-3` |
| `FormularioCatalogo` | Altas de obra, proveedor, insumo y demás catálogos | Un cambio de comportamiento en formularios ya probados | `soloLectura` es opcional y por omisión no cambia nada; `TC-INV-6` |
| `PantallaObras` | `linea-base.spec.ts` y `obras.spec.ts` (E2E de 012a y 018a) | Que el nuevo diálogo de acciones tape el botón «Línea base» | Las acciones van en su propia columna; los E2E existentes corren completos en B6 |
| Semilla de humo | `linea-base.spec.ts` congela su propia obra `E2E-LB-…` | Que las obras nuevas interfieran con ella | Cada prueba siembra y usa su obra; no comparten ninguna |

**Fronteras entre módulos:** No. `presupuesto` no importa a ningún módulo de negocio: el puerto es suyo y quien lo rellena es `servidor/`, que ya es la raíz de composición. `presupuesto` consume `auditoria.interfaz` (`asentar`, `AccionBitacora`) e `identidad.interfaz` (rol y sesión), que ya estaban en su grafo. Una fuente futura (por ejemplo `compras`) publicará una función en **su** `interfaz.py` y `servidor/fabrica.py` la inyectará; si ese cableado exigiera que `compras` importe `presupuesto`, la arista ya existe en `grafo-presupuesto` (`compras` es importador permitido), pero la inyección evita incluso eso.

## Documentación afectada

Qué se actualiza en **este mismo cambio** (durante `/sdd-ejecutar` y `/sdd-completar`; este diseño no los toca).

| Documento | Qué cambia |
|---|---|
| `docs/api/openapi.yaml` | Fila A8: `x-tickets`, `AccionBitacora` con `ELIMINAR`, `ObraCambios` cerrado, los `409` declarados, la descripción de `reactivar_obra` sin `(asumido)` |
| `docs/03-modelo-datos.md` | El enumerado `accion_bitacora` pasa de 23 a 24 verbos; la máquina de estados de `obra` (tabla de transiciones y qué estado bloquea la edición); la definición de «historial» y que el borrado de la obra es físico |
| `docs/07-especificacion-api.md` | Las cinco operaciones, los `409` y el verbo nuevo |
| `docs/04-historias-usuario.md` | Escenarios nuevos de HDU-001 si la persona dueña los quiere (la spec lo deja a su criterio); el escenario 20 no cambia |
| `docs/05-tickets-trabajo.md` | Cierre de la partición de TKT-012 y de los huecos de TKT-012a |
| `docs/08-wireframes.md` | Pantalla 2b: acciones de fila, formulario de edición, motivo, confirmación y bloqueo (fila B6) |
| `docs/adr/` y `docs/adr/README.md` | Los dos ADR de abajo |
| `CLAUDE.md:14` y `README.md:30` y `:283` | El conteo de ADR (hoy dicen 45; `docs/adr/` ya trae 46 archivos y con los dos nuevos serán 48): `verificar_docs.py` solo comprueba el índice, no el conteo, así que se corrige a mano |
| `docs/03-modelo-datos.md:1012` y `:1014` | «Veintitrés verbos» pasa a veinticuatro en la lista y en cualquier otro recuento del mismo párrafo |
| `docs/02-arquitectura.md` | Una nota en §5 sobre el puerto de historial inyectado desde la raíz de composición |
| `CLAUDE.md` | El recuento de verbos de la bitácora, si lo cita |

## ¿Merece ADR?

Sí, **dos**, que se escriben durante `/sdd-ejecutar` (A1 y A4):

1. `docs/adr/20261117-verbo-eliminar-y-borrado-fisico-de-la-obra.md` (A1). Alguien nuevo preguntaría por qué el borrado de la obra es físico cuando el del proveedor nunca lo es, y por qué un verbo nuevo y no `CANCELAR`/`ANULAR`. Opciones descartadas: borrado lógico (retiene `uq_obra_codigo` para siempre) y reutilizar un verbo existente (otro significado). Incluye la bajada con guarda, calcada de `0016`.
2. `docs/adr/20261117-historial-de-obra-por-puerto-inyectado.md` (A4). Opciones descartadas: importar las interfaces de los módulos posteriores desde `presupuesto` (rompe `grafo-presupuesto`), consultar sus tablas directamente (rompe la regla 3) y confiar solo en las claves foráneas (no da el conteo ni el mensaje, y dependería de cada tabla futura).

## Decisiones del diseño pendientes de la persona dueña

| # | Qué se ve | Opciones | Recomendación |
|---|---|---|---|
| D-DIS-1 | `CA-14` no ofrece «Cerrar» en `PLANEACION`, pero D-2 admite `PLANEACION → CERRADA`: sin el botón esa transición solo existiría por API | (a) `PLANEACION` ofrece Editar, Eliminar, Cerrar. (b) Dejar `CA-14` como está | **(a).** El diseño la implementa así y la fila de `CA-14` se corrige en la spec con su aprobación |
| D-DIS-2 | `CA-18` pide editar, suspender, reactivar **y** eliminar «la obra de línea base». Suspender exige `ACTIVA`, y `CA-14` solo ofrece Eliminar en `PLANEACION`: una misma obra no puede hacer las dos cosas | (a) Dos obras sembradas: M1 `ACTIVA` (línea base congelada) para editar, suspender y reactivar; M2 `PLANEACION` con línea base `BORRADOR` para el intento de eliminar. (b) Ofrecer Eliminar en todo estado salvo `CERRADA` y dejar que el servidor decida | **(a).** Mantiene `CA-14` y evita un botón que siempre fallaría en `ACTIVA` |
| D-DIS-3 | `CA-7` dice «exactamente una de las dos gana». Con historial amplio, una línea base `BORRADOR` materializada ya es historial: el borrado nunca gana, siempre responde `409` | (a) Leer `CA-7` como «el congelado gana, el borrado responde `409`, ninguna `500`», más una prueba de carrera real de borrado frente a una escritura de otro módulo (TC-56). (b) Redefinir historial para que una `BORRADOR` sin importación no cuente | **(a).** Es lo que obliga D-1; `CA-7` queda cubierto por TC-55 y TC-56 |
| D-DIS-4 | Una clave foránea hija (`23001`) hoy se traduce en `traducir_error_del_motor` a `ESTADO_NO_PERMITE_OPERACION`, genérico | (a) En `eliminar_obra`, traducirlo a `OBRA_CON_HISTORIAL`. (b) Dejar el genérico | **(a).** Es exactamente lo que el motor está diciendo; el detalle lleva el nombre de la restricción y no inventa un conteo |
| D-DIS-5 | D-1 dice «línea base no vacía de cualquier estado». Ninguna ruta crea una línea base vacía; el diseño consulta «existe alguna fila de `linea_base`» | (a) Así, por sencillez. (b) Contar sus hijas una a una | **(a)**, marcado `(asumido)` en la fila A2 hasta que la persona dueña confirme |
| D-DIS-6 | `CA-8` no lista `PLANEACION → CERRADA` en su tabla de ejemplos, aunque D-2 la admite | Añadir el ejemplo a `CA-8` | Sí; el diseño la prueba con TC-06 y TC-37 |
| D-DIS-7 | Dos pruebas existentes filtran por `x-tickets` exacto (`"TKT-012" in x-tickets`, `test_tkt017_api_congelado.py:1107`); el diseño cambia las cinco operaciones a `[TKT-012b]`. Además, el cableado de las fuentes de historial no tiene hoy ninguna fuente que cablear | (a) Ampliar el filtro de la prueba a `TKT-012b` y dejar el borrador en `[TKT-012b]`; añadir ya el parámetro `fuentes_historial` a `montar_presupuesto`. (b) Dejar `x-tickets: [TKT-012, TKT-012b]` y el cableado solo en el ADR | **(a).** El borrador dice la verdad sobre quién construye cada operación, y el parámetro cuesta cinco líneas y mantiene el puerto ejercitado de extremo a extremo |

**Resolución (2026-11-17).** La sesión que encargó este diseño comunicó que la persona dueña aprobó las recomendaciones de D-DIS-1 a D-DIS-7. Se aplicaron al texto de `spec.md` (`CA-7`, `CA-8`, `CA-14` y `CA-18`). El diseño no cambia: ya estaba escrito con esas recomendaciones.

## Pasada adversarial

Pasada de `abogado-del-diablo` (modo A, «diseñar»), 2026-11-17.

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | `revisor-impacto` halló que A1, A7 y B3 omitían pruebas existentes que el cambio pone en rojo (siete aserciones de «23 verbos», `CUERPOS_VALIDOS`, `IMPLEMENTADAS_DE_PRESUPUESTO`, la prueba de columnas de los lectores). Una fila que deja la suite en rojo no es un paso verificable | Incorporadas como ampliaciones declaradas en A1, A7, B3 y B4; D-DIS-7 |
| 2 | Alta | Carrera de borrado contra la **creación** de una importación: ese `INSERT` no bloquea la obra y, si el borrado confirma antes, falla con `23503`; la promesa «nunca un `500`» del diseño no estaba demostrada para esa ruta | R-9 y TC-56 por la ruta real; corrección mínima en ese caso de uso si responde `500` |
| 3 | Alta | `CA-7` («exactamente una gana») no puede cumplirse con historial amplio: una línea base `BORRADOR` ya es historial y el borrado nunca gana. El criterio, tal como está escrito, falla | D-DIS-3 y TC-55; se pide a la persona dueña reinterpretarlo |
| 4 | Media | `CA-14` y `CA-18` se contradicen: la obra de la prueba tendría que estar `ACTIVA` para suspenderse y en `PLANEACION` para ofrecer «Eliminar». `CA-14` además olvida «Cerrar» en `PLANEACION` | D-DIS-1 y D-DIS-2; la prueba E2E usa dos obras |
| 5 | Media | El puerto de historial sin ningún adaptador es código que nadie ejercita: la tupla vacía hace que `movimientos` siempre sea cero y un olvido futuro sea invisible. Alternativa descartada: no crear el puerto y confiar solo en la clave foránea | Se mantiene el puerto, con el parámetro cableable en `montar_presupuesto`, TC-32 que prueba la barrera de la clave foránea y el ADR que obliga al primer ticket que escriba una tabla con `obra_id` a publicar su fuente; R-1 |
| 6 | Media | Mutantes que habrían sobrevivido: la edición de una obra `SUSPENDIDA` (D-3) no tenía test propio y las acciones de `OBRA_CON_HISTORIAL` desde `PLANEACION` podían pasar con una implementación equivocada | TC-22 cubre `SUSPENDIDA`; TC-31 fija las acciones por estado; ambos en la tabla de mutantes |
| 7 | Baja | La semilla que congela desde `herramientas/` depende de que `congelar` funcione con los datos sintéticos `(sin ejecutar)` | La verificación de B5 lo comprueba antes de B6; si no sirve, B6 congela la obra con `POST /lineas-base/{id}/congelacion` desde la prueba |

Observaciones de evolución consultadas: la ampliación declarada de pruebas existentes al añadir un verbo de bitácora ya ocurrió con `0016` (TKT-029b) y se repite aquí; se anota para `meta-sdd` como patrón de tres o más apariciones.

## Riesgos

| # | Riesgo | Probabilidad | Impacto | Qué se hace |
|---|---|---|---|---|
| R-1 | Hoy ningún módulo posterior publica una fuente de historial; `requisicion`, `orden_compra` y `solicitud_autorizacion` ya existen en el esquema | Media | Alto: si un ticket posterior escribe esas tablas y olvida publicar la fuente, el conteo de `movimientos` sale en cero | La clave foránea `RESTRICT` sigue siendo la barrera y TC-32 lo demuestra. El ADR del puerto exige que el primer ticket que escriba una tabla con `obra_id` publique su fuente; se anota en el `delta.md` |
| R-2 | `archivo.obra_id` no tiene clave foránea: un archivo huérfano apuntaría a una obra borrada | Baja (`archivos` aún no tiene escritores) | Medio | La fuente de historial de `archivos` es condición del ticket que lo escriba (mismo ADR) |
| R-3 | Nada impide por esquema una transición inválida escrita por otro camino (por ejemplo `UPDATE obra SET estado` a mano) | Baja | Medio | Se acepta: el congelado y el mantenimiento pasan por `FOR UPDATE` y por el dominio. Un disparador sería un invariante nuevo del modelo de datos y se propone como ticket futuro, no se añade aquí |
| R-4 | La bajada de `0017` no es automática con asientos `ELIMINAR` | Baja | Medio | Documentado en el ADR y en la docstring, igual que `0016`; el plan de reversa pide respaldo y decisión |
| R-5 | Qué hacen los demás módulos con una obra `SUSPENDIDA` o `CERRADA` no está decidido (S-3): hoy se podría importar o capturar una requisición contra una obra cerrada | Media | Medio | Fuera del alcance; se registra como ticket futuro en el hub y se avisa a la persona dueña en el gate |
| R-6 | La otra sesión que diseña TKT-032a podría también necesitar una migración y reclamar la revisión `0017` | Baja | Bajo | El diseño de TKT-032a es solo de pantalla de proveedores y no declara migración; si se cruzaran, la segunda en ejecutarse renumera. A1 comprueba `alembic heads` antes de crear el archivo |
| R-7 | La prueba E2E de humo acumula obras (límite de 200 por página, ya conocido en `obras.spec.ts`) | Baja | Bajo | Las obras de mantenimiento se abren por código en la lista y, si el filtro no las alcanza, por URL directa como hace `linea-base.spec.ts` |
| R-9 | El borrado compite con la **creación** de una importación (`importacion.obra_id`), que no bloquea la obra: si el borrado confirma primero, el `INSERT` hijo falla con `23503` y, según la ruta, saldría un `500`. La materialización sí bloquea la obra (`materializacion.py:146`) y queda serializada | Baja | Medio | TC-56 se ejecuta también por la ruta real de creación de importación; si responde `500`, es un defecto expuesto por este ticket y se corrige en él con el cambio mínimo (traducir `23503` a `404 NO_ENCONTRADO` en ese caso de uso) y se anota en «Ajustes de la ejecución» |
| R-8 | Dos pestañas editan la misma obra: gana la última sin aviso (sin control optimista) | Media | Bajo | Supuesto 4 de la spec; se acepta en la fase 1 |

## Ajustes de la ejecución

Vacío mientras no haya ninguno.
