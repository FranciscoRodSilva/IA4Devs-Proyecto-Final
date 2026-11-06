# Design · TKT-017 · Confirmación y congelado de la línea base

> [← index](_index.md) | [← spec](spec.md) | Siguiente: `impl.md` (lo escribe `/sdd-ejecutar`)

## Estrategia

Tres entregas que se fusionan en orden, cada una con su rama y su bloque de filas: **TKT-017a** materializa una importación `VALIDADO` en la jerarquía real y una línea base `BORRADOR`; **TKT-017b** congela esa línea base, publica sus cuatro lecturas y monta el módulo en la API; **TKT-017c** captura y recaptura el tope de control. Todo el ciclo de vida de la línea base de una obra —confirmar, reemplazar, congelar— se serializa con un único bloqueo pesimista: `SELECT … FOR UPDATE` sobre la fila de `obra`, tomado después del de la importación y antes que el de la línea base, siempre en ese orden; la recaptura del tope bloquea su fila de `presupuesto_control`, como pide [ADR-004](../../../docs/adr/20260918-bloqueo-pesimista-presupuesto.md). La materialización cuantiza cada valor a la escala de su columna **antes** de calcular importes y explosión, y una sola función de dominio, `explotar_filas`, calcula la explosión de validación al confirmar y la explosión congelada al congelar: por construcción, las dos reciben los mismos números y `CA-B1` se cumple renglón por renglón. Los `SQLSTATE` del motor se traducen en un solo punto de `aplicacion/`, que nace en TKT-017a porque la confirmación ya necesita `55P03`.

Consultas a Context7, el 2026-11-05: SQLAlchemy 2.1 (`DBAPIError.orig`, `Session.begin()` que deshace ante una excepción, `with_for_update()` en Core) y Pydantic v2 (`model_validator`, `extra_forbidden`, `too_short` con `min_length`). De la segunda sale una decisión: un `ValueError` de un `model_validator` se ubica en `()` y el manejador lo traduce como `FORMATO` en `cuerpo`, así que los `422` con campo y `OBLIGATORIO` que exigen `CA-A3`, `CA-A8`, `CA-C3` y `CA-C5` los lanza el caso de uso con `ValidacionRechazada`, no un validador del DTO.

## Escalera de decisión

| Objeto | Peldaño donde paró | Por qué |
|---|---|---|
| Bloqueo `FOR UPDATE` sobre la fila de `obra` en confirmar y congelar | 2 · nativo | Bloqueo de fila del motor, con el `lock_timeout` de 5 s que el rol de aplicación ya lleva (`v0001`). El índice único parcial `uq_linea_base_obra_id_congelada` (invariante 5) solo cubre dos congelados; no impide dos `BORRADOR` ni un congelado que copie una jerarquía que otra sesión está borrando (`CA-A10`, `CA-B6` esc. 3). Ver «¿Merece ADR?» |
| Índice único parcial sobre `BORRADOR` por obra | 1 · YAGNI, fuera | Cubriría `CA-A10` pero no `CA-B6` esc. 3, que de todos modos exige el bloqueo de la obra; y la segunda confirmación chocaría antes con `uq_concepto_obra_id_codigo`, que el traductor no puede atribuir a un borrador |
| `pg_advisory_xact_lock` por obra | 1 · YAGNI, fuera | Resuelve lo mismo que el bloqueo de fila con una clave numérica derivada que puede colisionar y que no aparece en `pg_locks` como fila de `obra` |
| `FOR UPDATE` sobre `presupuesto_control` en la recaptura | 3 · reuso | El patrón de ADR-004; el privilegio `UPDATE` que lo permite lo conserva `v0007` a propósito |
| `backend/migraciones/versions/v0011_presupuesto_campos_sin_fuente.py` | 4 · cambio mínimo | `ALTER COLUMN … DROP NOT NULL` en las cinco columnas que fija `A-M7`; no toca ningún invariante: ninguno de los 39 exige esos `NOT NULL` |
| Guarda de la bajada de `0011` | 3 · reuso | El patrón `DO` con `LOCK TABLE` y `RAISE EXCEPTION` de `0007` y `0010`, con `SQLSTATE` `P0001` |
| `preparacion_desde_json` en `infraestructura/preparacion_json.py` | 4 · cambio mínimo | Inversa de `preparacion_a_json`, en el mismo archivo. Devuelve el `Preparacion` de dominio que ya existe |
| `FormatoPreparacionDesconocido` | 5 · objeto nuevo | Excepción de infraestructura de una línea; el caso de uso la convierte en `ESTADO_NO_PERMITE_OPERACION` |
| `dominio/explosion_materializada.py` · `FilaExplotable`, `InsumoDeApu`, `CargoDeApu`, `explotar_filas` | 5 · objeto nuevo | Adaptador puro que arma `ConceptoAExplotar` desde valores ya cuantizados y llama a `calcular_explosion` sin cambiarla. Es lo que hace que la explosión de validación y la congelada sean la misma función sobre los mismos números |
| `dominio/materializacion.py` · `planificar_materializacion` y sus objetos de valor | 5 · objeto nuevo | Ninguna regla existente convierte una preparación en filas. Pura: recibe el generador de identificadores, no lo crea |
| `dominio/captura_tope.py` · `evaluar_captura_tope` | 5 · objeto nuevo | La decisión primera captura / recaptura / tope superior a la venta es regla (`PA-03`, `RN-03`, `RN-04`, HDU-001 esc. 17) y va en dominio |
| Tablas Core en `infraestructura/tablas.py` | 4 · cambio mínimo | El archivo ya declara `importacion`, `importacion_error` e `insumo` con la convención de nombres; se añaden las once tablas que el ticket lee o escribe, solo con las columnas que usa |
| `infraestructura/repositorio_linea_base.py` | 5 · objeto nuevo | No existe repositorio de jerarquía ni de línea base. Uno solo para las tres entregas: cada entrega añade sus funciones |
| `aplicacion/traduccion_motor.py` · `traducir_error_del_motor` | 5 · objeto nuevo | ADR-031 encarga la traducción a TKT-017 y no existe ninguna. Vive en `aplicacion/` de `presupuesto` porque los detalles de `RN-01` necesitan leer la obra; no en `contrato_error`, que es puro y no conoce `sqlalchemy` |
| `aplicacion/contexto.py` · `ContextoPresupuesto` | 3 · reuso | Mismo patrón que `ContextoIdentidad`: fábrica de sesiones perezosa y reloj inyectado |
| `aplicacion/materializacion.py` · `materializar_importacion` | 5 · objeto nuevo | El caso de uso de `A-M1`, publicado en `interfaz.py` |
| `aplicacion/congelado.py` · `congelar_linea_base` | 5 · objeto nuevo | El caso de uso de `B-M1` |
| `aplicacion/consulta_linea_base.py` | 5 · objeto nuevo | Las cuatro lecturas de `B-M4` y la lectura de control de `C-M1` |
| `aplicacion/presupuesto_control.py` · `capturar_tope` | 5 · objeto nuevo | El caso de uso de `C-M2` y `C-M3` |
| `api/esquemas.py`, `api/rutas_linea_base.py`, `api/rutas_presupuesto_control.py`, `api/montaje.py` | 5 · objeto nuevo | `presupuesto/api/` está vacío. `montaje.py` sigue el patrón de `identidad` |
| `montar_presupuesto` en `servidor/fabrica.py` | 4 · cambio mínimo | Una llamada más, junto a `montar_identidad` |
| Protección de rutas | 3 · reuso | `verificar_origen` y `exigir_rol` de `cimenta.identidad.interfaz`; `exigir_rol` ya asienta el `403` como `DENEGAR` (`CA-B4`, `CA-C5`) |
| Bitácora | 3 · reuso | `asentar` y `consultar_bitacora` de `cimenta.auditoria.interfaz`, en la sesión del caso de uso |
| `nombres_de_usuarios` y `UsuarioResumen` en `cimenta.identidad.interfaz` | 3 · reuso si TKT-059 ya los publicó; 5 · objeto nuevo si no | `UsuarioResumen` necesita el nombre y `presupuesto` no puede leer la tabla `usuario`. Una función de lectura de unas 25 líneas y un modelo de dos campos, compartidos con TKT-059 (decisión «Coordinación con TKT-059» de `_index.md`) |
| Columna `linea_base.importacion_id` | 1 · YAGNI, fuera (`P-5`) | El asiento `DESCARTAR` necesita la importación del borrador; se obtiene del asiento `CONFIRMAR` por `consultar_bitacora` sin tocar el esquema |
| Columna `explosion_presupuesto.importe_venta` | 4 · cambio mínimo, solo documental | Se documenta como cantidad × costo unitario; no se renombra en el esquema (`CA-B9`) |
| Traducción de `42501` (`PA-T17.10`) | 1 · YAGNI, fuera | Ninguna ruta emite `UPDATE` ni `DELETE` sobre `linea_base_concepto`: el reemplazo nunca la toca (ver «Orden de borrado») y el congelado solo inserta. Un `42501` sería un error de programa y debe llegar como `500` a Sentry, no disfrazarse de regla. Decisión del diseño; el mutante `M-A6` la protege |
| Fábrica `datos_presupuesto.importacion(preparacion=…)` y `herramientas/soporte_tkt017.py` | 4 · cambio mínimo y 5 · nuevo | Un argumento más en la fábrica existente; el soporte arma preparaciones sintéticas en memoria (decisión de la persona dueña: libros sintéticos) |
| ADR nuevo | 5 · objeto nuevo | Ver «¿Merece ADR?» |

Ningún objeto paró en el peldaño 4 tocando un invariante: `0011` relaja columnas que ningún invariante protege, y los disparadores, el índice parcial y la revocación de `v0007` no se modifican.

## Decisiones de diseño que la ejecución no reabre

### Orden de comprobaciones de la materialización

Todo antes de la primera escritura, en este orden; cada rechazo deja la transacción sin escribir y la deshace.

1. `bloquear_importacion` (existe). Sin fila → `NoEncontrado(recurso="importacion")`.
2. Estado `CON_ERRORES` → `CONFLICTO` `IMPORTACION_CON_ERRORES`; cualquier otro distinto de `VALIDADO` → `ESTADO_NO_PERMITE_OPERACION` con `{"importacion_id", "estado"}`.
3. `bloquear_obra(obra_id)` → `SELECT id, codigo, nombre, estado FROM obra WHERE id = :obra FOR UPDATE`.
4. Línea base `CONGELADA` en la obra → `ESTADO_NO_PERMITE_OPERACION` con `{"obra", "linea_base_vigente_id", "version_vigente"}`. Va antes que el estado de la obra porque una obra con congelada está `ACTIVA` y `CA-A4` esc. 1 exige el mensaje de la congelada.
5. Obra distinta de `PLANEACION` → `ESTADO_NO_PERMITE_OPERACION` con `{"obra", "estado_obra"}`.
6. Hay `BORRADOR`: sin `reemplazar_borrador` → `REEMPLAZO_NO_CONFIRMADO`; con él y motivo nulo o en blanco → `422` `OBLIGATORIO` en `motivo_reemplazo`. Sin borrador, `reemplazar_borrador` se ignora.
7. `preparacion_desde_json`. Formato distinto de 1, clave ausente o tipo inesperado → `ESTADO_NO_PERMITE_OPERACION`.
8. `planificar_materializacion`, que devuelve el primer rechazo en este orden: asignación (`422`), preparación inconsistente, insumo en conflicto, explosión rechazada.

### Orden de comprobaciones del congelado

1. Leer la línea base sin bloqueo para conocer su obra. Sin fila → `NoEncontrado(recurso="linea_base")`.
2. `bloquear_obra`. Después, `bloquear_linea_base` (`FOR UPDATE`); si ya no existe, porque un reemplazo la borró mientras esperaba, `NoEncontrado(recurso="linea_base")` (`CA-B6` esc. 3).
3. Estado distinto de `BORRADOR` → `ESTADO_NO_PERMITE_OPERACION` con `{"linea_base_id", "estado"}`.
4. Otra línea base `CONGELADA` en la obra → `REGLA_NEGOCIO` `RN-01` (`CA-B2`). Va antes que el estado de la obra por la misma razón que en la materialización.
5. Obra distinta de `PLANEACION` → `ESTADO_NO_PERMITE_OPERACION` con `{"obra", "estado_obra"}`.
6. Explosión desde las filas materializadas; si `explotar_filas` rechaza → `ESTADO_NO_PERMITE_OPERACION` con las causas (defensivo: la confirmación ya la validó).

### Orden de borrado del reemplazo

Todas las claves foráneas son `ON DELETE RESTRICT`, así que se borra de las hojas a la raíz, siempre filtrando por la obra:

1. `apu_cargo` cuyo `apu_id` pertenece a un `apu` de un `concepto` de la obra.
2. `apu_insumo`, con el mismo filtro.
3. `apu` cuyo `concepto_id` es de la obra.
4. `partida_concepto` cuyo `concepto_id` es de la obra.
5. `concepto` de la obra.
6. `partida` cuya `area` cuelga de un `nivel` de la obra.
7. `area` cuyo `nivel` es de la obra.
8. `nivel` de la obra.
9. `linea_base` del borrador, por `id`. El disparador admite el `DELETE` de un `BORRADOR`.

**Nunca** se emite `DELETE` sobre `linea_base_concepto`, `explosion_presupuesto` ni `presupuesto_control`: un borrador no tiene copias ni control (solo los crea el congelado, que lo pasa a `CONGELADA` en la misma transacción), y sobre `linea_base_concepto` el rol de aplicación ni siquiera tiene `DELETE`, que rechaza la sentencia con `42501` aunque no afecte ninguna fila (`E-2`). Si alguna fila sembrada a mano los referencia, el paso 4 o el 9 fallan con `23001` y el traductor responde `ESTADO_NO_PERMITE_OPERACION`. Los insumos y `precio_insumo` no se tocan.

La versión nueva se calcula **después** del borrado: `SELECT COALESCE(MAX(version), 0) + 1 FROM linea_base WHERE obra_id = :obra`.

### Cuantización antes de calcular (`P-4`)

`planificar_materializacion` cuantiza con `cuantizar()` cada valor que va a una columna, a la escala de esa columna, y calcula todo lo demás con los valores ya cuantizados: `partida_concepto.importe = (cantidad_q × precio_unitario_q).cuantizar()`, `linea_base.importe_venta = Σ importe_q`, y la explosión de validación sobre cantidades, costos, rendimientos e importes de cargo cuantizados. El congelado lee esos mismos números de la base. Así lo validado es exactamente lo congelado. Calcular sobre la preparación sin cuantizar daría centavos de diferencia en cuanto una celda del Excel traiga más decimales que su columna.

### Insumos (`P-6`)

`planificar_materializacion` resuelve cada clave de insumo de los análisis contra los insumos registrados (`id`, `codigo`, `descripcion`, `unidad`, `tipo`):

- **Insumo por crear** (`preparacion.insumos_por_crear`): busca el registrado con `codigo == clave`. Si existe con la misma unidad y el mismo tipo, lo reutiliza sin tocar su `creado_en_importacion`; si difiere, `InsumoEnConflicto` (`PA-T13`). Si no existe, lo crea con `codigo = clave`, `activo = true` y `creado_en_importacion = true`.
- **Insumo ya registrado**: lo busca por `normalizar_clave_insumo(descripcion) == clave`, el mismo criterio de `mapa_de_insumos_existentes` (gana el primero por `codigo`). Si no aparece, `PreparacionInconsistente` («la importación debe analizarse de nuevo»). Si su unidad o su tipo difieren de los del análisis, `InsumoEnConflicto`.

La explosión usa como clave el `codigo` del insumo resuelto, de modo que al confirmar y al congelar los renglones se agrupan por la misma clave.

### Bitácora

| Caso | `accion` | `entidad_tipo` · `entidad_id` | `regla_negocio` | `motivo` | Datos |
|---|---|---|---|---|---|
| Confirmación | `CONFIRMAR` | `linea_base` · la nueva | — | — | `datos_despues`: `importacion_id`, `version`, `importe_venta` (cadena) |
| Reemplazo | `DESCARTAR` | `linea_base` · la descartada | — | el de reemplazo | `datos_antes`: `estado` `BORRADOR`, `version`, `importacion_id` (cadena o nulo) |
| Congelado | `CONGELAR` | `linea_base` | `RN-01` | el de congelado | `datos_antes` `{"estado": "BORRADOR"}`; `datos_despues` `{"estado": "CONGELADA", "version", "importe_venta"}` |
| Primera captura | `CREAR` | `presupuesto_control` · la fila | — | el recibido, si lo hay | `datos_despues`: `tipo_partida`, `importe_tope` |
| Recaptura | `RECAPTURAR` | `presupuesto_control` · la fila | `RN-03` | obligatorio | `datos_antes` `{"importe_tope"}`; `datos_despues` `{"importe_tope"}` |

Todos con `obra_id` y `ocurrido_en` del reloj del contexto. El `importacion_id` del `DESCARTAR` se lee, antes de borrar, con `consultar_bitacora(sesion, entidad_tipo="linea_base", entidad_id=borrador_id, accion=("CONFIRMAR",), tamano_pagina=1)`; un borrador sembrado sin asiento lo deja nulo (`P-5`).

### Traducción del motor

`traducir_error_del_motor(error: DBAPIError, *, ruta_reintento: str, metodo_reintento: str, roles_reintento: tuple[str, ...], rechazo_vigente: Callable[[], ErrorContrato]) -> ErrorContrato | None`. Lee `getattr(error.orig, "sqlstate", None)` y `error.orig.diag.constraint_name`. El caso de uso envuelve su `with fabrica.begin()` en `try/except DBAPIError`, y si el traductor devuelve `None` relanza el original.

| `SQLSTATE` | Condición | Respuesta |
|---|---|---|
| `IN001` | cualquiera | `RechazoRegla(regla="RN-01", mensaje="La línea base congelada no se modifica.", detalle={"tabla": diag.table_name}, acciones=())` |
| `23505` | `constraint_name == "uq_linea_base_obra_id_congelada"` | `rechazo_vigente()`: abre otra transacción corta, lee la obra y su vigente y devuelve el mismo `RechazoRegla` `RN-01` de `CA-B2` |
| `23505` | otra restricción | `ConflictoEstado` `ESTADO_NO_PERMITE_OPERACION` con `{"restriccion": constraint_name}` (`P-7`) |
| `55P03` | — | `ConcurrenciaVencida(codigo="BLOQUEO_VENCIDO", mensaje="Otra operación está usando la línea base de esta obra en este momento. Vuelve a intentarlo.", espera_maxima_ms=5000, reintentar_en_s=1, acciones=[Accion("REINTENTAR", metodo_reintento, ruta_reintento, roles_reintento)])` |
| `57014` | — | Igual, con `codigo="TIEMPO_EJECUCION_VENCIDO"` y `espera_maxima_ms=15000` (`P-7`) |
| `23503`, `23001` | — | `ConflictoEstado` `ESTADO_NO_PERMITE_OPERACION` con `{"restriccion": constraint_name}` |
| otro, incluido `42501` | — | `None`: se relanza y responde `500` sin `tipo` |

`5000` y `15000` son el `lock_timeout` y el `statement_timeout` del rol de aplicación en `v0001`.

### Mensajes y detalles exactos

| Rechazo | `mensaje` | `detalle` | `acciones` |
|---|---|---|---|
| `IMPORTACION_CON_ERRORES` | «La importación tiene errores bloqueantes y no se confirma.» | `importacion_id`, `estado` | — |
| Importación en otro estado | «La importación está en {estado} y no se confirma. Solo se confirma una importación VALIDADO.» | `importacion_id`, `estado` | — |
| Obra con congelada | «La obra {codigo} ya tiene una línea base congelada; no admite otra importación.» | `obra` («{codigo} · {nombre}»), `linea_base_vigente_id`, `version_vigente` | — |
| Obra fuera de planeación | «La obra {codigo} está en {estado} y no admite esta operación.» | `obra`, `estado_obra` | — |
| `REEMPLAZO_NO_CONFIRMADO` | «La obra ya tiene una línea base en borrador; confirmar esta importación la reemplaza.» | `linea_base_borrador_id`, `version` | `CONFIRMAR_REEMPLAZO` · `POST` · `/api/v1/importaciones/{id}/confirmacion` · `DIRECTOR_PROYECTOS` |
| Formato o preparación ilegible | «La preparación de la importación no se puede leer; la importación debe analizarse de nuevo.» | `importacion_id`, `formato` (el leído o nulo) | — |
| Insumo en conflicto | «El insumo {codigo} ya existe con otra unidad o tipo; la importación debe analizarse de nuevo.» | `codigo`, `unidad_importacion`, `tipo_importacion`, `unidad_registrada`, `tipo_registrado` | — |
| Explosión rechazada | «La explosión de insumos de la importación no se puede calcular.» | `importacion_id` (o `linea_base_id` al congelar), `causas`: lista de `{"concepto", "causa", "clave_insumo", "tipo_partida_id"}` con nulos donde no aplica. `SUGERIDO_NEGATIVO` es una causa por tipo de partida: `_causas_de_sugerido` la crea con `codigo_concepto=None` y el `tipo_partida_id` del tipo, así que su `concepto` es nulo; las causas por concepto (`CARGO_AUSENTE`, `INSUMO_SIN_COSTO`, `SIN_ANALISIS` y las demás de `_causas_de_concepto`) llevan el código del concepto | — |
| Línea base en otro estado | «La línea base está en {estado}; solo se congela una línea base en BORRADOR.» | `linea_base_id`, `estado` | — |
| `RN-01` al congelar | «La obra {codigo} ya tiene una línea base congelada; para sustituirla hay que crear una versión nueva que marque la anterior como SUPERSEDIDA.» | `obra`, `linea_base_vigente_id`, `version_vigente` | `[]` |
| `SIN_LINEA_BASE_CONGELADA` | «La línea base está en {estado}; el tope solo se captura sobre una línea base congelada.» | `linea_base_id`, `estado` | — |
| `TOPE_SUPERIOR_A_VENTA_SIN_CONFIRMAR` | «El tope de {clave} supera su importe de venta; implicaría vender por debajo del costo tope.» | `tipo_partida` (clave), `importe_venta`, `importe_tope` (`Dinero` cuantizados) | `CONFIRMAR_TOPE_SUPERIOR` · `PUT` · ruta de la operación · `DIRECCION_GENERAL` |

`NoEncontrado` exige `mensaje` (`contrato_error/excepciones.py`, línea 345). Cada uso lleva el suyo:

| `recurso` | `mensaje` | Dónde |
|---|---|---|
| `importacion` | «La importación no existe.» (el mismo de `iniciar_analisis`) | materialización |
| `obra` | «La obra no existe.» | `listar_lineas_base` |
| `linea_base` | «La línea base no existe.» | congelado (también cuando un reemplazo la borró mientras esperaba), las cuatro lecturas y la captura |
| `tipo_partida` | «El tipo de partida no existe.» | captura del tope |
| `presupuesto_control` | «La línea base no tiene presupuesto de control para ese tipo de partida.» | captura, si la fila no existe (defensivo: una congelada siempre tiene las cuatro) |

Campos de los `422` lanzados por el caso de uso: `asignacion_tipos_partida.{nombre}` (`OBLIGATORIO` «Falta el tipo de partida de esta partida.» o `VALOR_NO_PERMITIDO` «El tipo de partida no existe.»), `motivo_reemplazo` y `motivo` (`OBLIGATORIO` «El campo es obligatorio.»).

## Capas afectadas

### Dominio

| Archivo | Qué | Regla |
|---|---|---|
| `cimenta/presupuesto/dominio/explosion_materializada.py` | `InsumoDeApu(codigo: str, tipo: TipoInsumo, unidad: str, costo_unitario: Dinero, rendimiento: Rendimiento)`, `CargoDeApu(tipo: TipoCargo, importe: Dinero)`, `FilaExplotable(codigo_concepto: str, tipo_partida_id: UUID, cantidad: Cantidad \| None, precio_unitario: Dinero \| None, insumos: tuple[InsumoDeApu, ...] \| None, cargos: tuple[CargoDeApu, ...])` (`insumos is None` es «sin análisis»). `explotar_filas(filas: Sequence[FilaExplotable]) -> ExplosionCalculada \| RechazoExplosion`: llama a `calcular_explosion` y, si no rechaza, devuelve `.cuantizar()`. Por cada fila, con `n = índice + 1`, arma exactamente estos objetos del lector (campos verificados en `dominio/catalogo.py` y `dominio/analisis.py`): `ConceptoAExplotar(concepto=ConceptoLeido(fila=n, codigo=codigo_concepto, descripcion=None, unidad=None, cantidad=cantidad, precio_unitario=precio_unitario, importe=None, ruta=Ruta(raiz=None, nivel=None, area=None, partida=None)), tipo_partida_id=tipo_partida_id, analisis=None si insumos is None, si no AnalisisLeido(hoja=codigo_concepto, cabecera=CabeceraLeida(fila_codigo=None, codigo=None, unidad=None, fecha=None, analista=None, precio_unitario=None), insumos=…, cargos=…, fila_precio_unitario=0, precio_unitario=precio_unitario, totales=TotalesAnalisis(material=None, mano_obra=None, costo_directo=None, cargos=None, precio_unitario=None), hallazgos=()))`. Cada insumo: `InsumoLeido(fila=0, tipo=tipo, descripcion=codigo, clave=codigo, unidad=unidad, costo_unitario=costo_unitario, rendimiento=rendimiento, cargo=None)`. Cada cargo: `CargoLeido(fila=0, rotulo=tipo.value, tipo=tipo, porcentaje=None, base=None, importe=importe)` | `RN-24`, `PA-01`, `PA-03`, `PA-23` |
| `cimenta/presupuesto/dominio/materializacion.py` | Objetos de valor `InsumoRegistrado`, `NivelNuevo(id, nombre, orden)`, `AreaNueva(id, nivel_id, nombre)`, `PartidaNueva(id, area_id, tipo_partida_id, orden)`, `ConceptoNuevo(id, codigo, descripcion, unidad)`, `PartidaConceptoNueva(id, concepto_id, partida_id, cantidad, precio_unitario, importe)`, `InsumoNuevo`, `ApuNuevo` con `ApuInsumoNuevo` y `ApuCargoNuevo`, `PlanMaterializacion(…, importe_venta: Dinero, explosion: ExplosionCalculada)`. Rechazos `AsignacionInvalida(faltantes: tuple[str, ...], inexistentes: tuple[str, ...])`, `PreparacionInconsistente(motivo: str, codigo_concepto: str \| None)`, `InsumoEnConflicto(codigo, unidad_importacion, tipo_importacion, unidad_registrada, tipo_registrado)`, `ExplosionRechazada(causas)`. Función `planificar_materializacion(preparacion: Preparacion, *, asignacion: Mapping[str, UUID], tipos_partida: frozenset[UUID], insumos_registrados: Sequence[InsumoRegistrado], nuevo_id: Callable[[], UUID]) -> PlanMaterializacion \| RechazoMaterializacion` | `RN-01`, `PA-T8`, `PA-T13`, `PA-T17` |
| `cimenta/presupuesto/dominio/captura_tope.py` (c) | `CausaRechazoCaptura` (`TOPE_SUPERIOR_SIN_CONFIRMAR`, `MOTIVO_OBLIGATORIO`), `CapturaAdmitida(es_recaptura: bool)`, `CapturaRechazada(causa)`. `evaluar_captura_tope(*, tope_anterior: Dinero \| None, tope_nuevo: Dinero, importe_venta: Dinero, motivo: str \| None, confirmar_superior_a_venta: bool) -> CapturaAdmitida \| CapturaRechazada`. Orden: si `tope_nuevo.valor > importe_venta.valor` y no confirma → `TOPE_SUPERIOR_SIN_CONFIRMAR`; si (supera y confirma) o es recaptura, y el motivo es nulo o en blanco → `MOTIVO_OBLIGATORIO`; si no, admitida. Igual a la venta no exige confirmación | `PA-03`, `RN-03`, `RN-04` |

Reglas de `planificar_materializacion`, en este orden:

1. **Estructura.** Cada concepto necesita ruta con nivel, área y partida con nombre, descripción, unidad y una única hoja de análisis asociada por su fila; dos filas con el mismo código en la misma partida también son inconsistencia. Cualquier fallo → `PreparacionInconsistente`.
2. **Asignación.** Los nombres requeridos son los de las partidas que alcanza algún concepto. Faltante → `faltantes`; tipo que no está en `tipos_partida` → `inexistentes`. Las claves de la asignación que no corresponden a ninguna partida se ignoran (`P-12`).
3. **Insumos**, según «Insumos».
4. **Explosión de validación** con `explotar_filas` sobre los valores cuantizados, una `FilaExplotable` por concepto del catálogo, en orden de fila.
5. **Filas.** `nivel.orden` es la posición, desde 1, de cada nivel distinto ordenado por su fila; `partida.orden`, la posición dentro de su área. Solo se crean los nodos que alcanza algún concepto. Un `ConceptoNuevo` por código distinto, con descripción y unidad de su primera aparición. Un `PartidaConceptoNueva` por concepto del catálogo con el precio unitario **del pie de su análisis**. Un `ApuNuevo` por concepto, con su hoja. `area.tipo_unidad`, `apu.fecha_analisis` y `apu.analista` nulos si la preparación no los trae; `fecha_analisis` viaja como la cadena `AAAA-MM-DD` del lector y la convierte la infraestructura.

**Mapeo del análisis a `apu`, `apu_insumo` y `apu_cargo`** (decisión de la persona dueña del 2026-11-06), todo cuantizado a la escala de su columna:

| Columna | Origen en la preparación |
|---|---|
| `apu.costo_material` | `totales.material` |
| `apu.costo_mano_obra` | `totales.mano_obra` |
| `apu.costo_directo` | `totales.costo_directo` |
| `apu.total_cargos` | `totales.cargos` |
| `apu.total_indirectos` | Suma de los `importe` de los cargos de tipo `INDIRECTOS` (`0.0000` si no hay ninguno) |
| `apu.precio_unitario` | `AnalisisLeido.precio_unitario`, el del pie |
| `apu.fecha_analisis` · `apu.analista` | `cabecera.fecha` · `cabecera.analista`, nulos si faltan |
| `apu_insumo.costo_unitario` · `rendimiento` · `cargo` | `InsumoLeido.costo_unitario` · `rendimiento` · `cargo` |
| `apu_cargo.tipo` · `porcentaje` · `base_calculo` · `importe` | `CargoLeido.tipo` · `porcentaje` · `base` · `importe`; `porcentaje` y `base_calculo` nulos si faltan |

Un nulo en `apu.costo_material`, `costo_mano_obra`, `costo_directo`, `total_cargos` o `precio_unitario`, en `apu_insumo.costo_unitario`, `rendimiento` o `cargo` (también en los insumos de mano de obra), o en `apu_cargo.tipo` o `importe`, se rechaza en el paso 1 con `PreparacionInconsistente`, con el código del concepto y el nombre de la columna en `motivo` («la importación debe analizarse de nuevo»). Ninguno de esos nulos llega a la base.

### Aplicación

| Archivo | Caso de uso | Transacción y bloqueo |
|---|---|---|
| `aplicacion/contexto.py` | `ContextoPresupuesto(fabrica_sesiones: Callable[[], sessionmaker[Session]], reloj: Callable[[], datetime])` y `construir_contexto(*, proveedor_motor, reloj)`, con `datetime.now(UTC)` por omisión | — |
| `aplicacion/traduccion_motor.py` (a) | `traducir_error_del_motor`, según «Traducción del motor» | No abre transacción salvo `rechazo_vigente`, que abre una corta de solo lectura |
| `aplicacion/materializacion.py` (a) | `materializar_importacion(contexto: ContextoPresupuesto, *, importacion_id: UUID, asignacion_tipos_partida: Mapping[str, UUID], reemplazar_borrador: bool, motivo_reemplazo: str \| None, usuario_id: UUID) -> LineaBaseMaterializada(importacion_id, linea_base_id, version, importe_venta: Dinero)` | Una sola `fabrica.begin()`. Bloqueos: importación → obra. Llama al repositorio **por atributo del módulo** (`repositorio_linea_base.insertar_niveles(…)`), para que las pruebas puedan provocar el fallo a mitad y la pausa con `monkeypatch` |
| `aplicacion/congelado.py` (b) | `congelar_linea_base(contexto, *, linea_base_id: UUID, motivo: str, usuario_id: UUID) -> UUID` | Una transacción. Bloqueos: obra → línea base. Orden de escritura: copiar conceptos, insertar explosión, insertar controles, actualizar línea base, actualizar obra, asentar |
| `aplicacion/consulta_linea_base.py` (b y c) | `listar_lineas_base(contexto, obra_id)`, `obtener_linea_base(contexto, linea_base_id)`, `listar_conceptos(contexto, linea_base_id, *, tipo_partida_id, nivel, q, pagina, tamano_pagina)`, `obtener_explosion(contexto, linea_base_id, *, tipo_partida_id)` y, en c, `listar_presupuesto_control(contexto, linea_base_id)` | Una transacción de lectura por llamada, sin bloqueo |
| `aplicacion/presupuesto_control.py` (c) | `capturar_tope(contexto, *, linea_base_id, tipo_partida_id, importe_tope: Dinero, motivo: str \| None, confirmar_superior_a_venta: bool, usuario_id: UUID) -> UUID` | Una transacción. Lee la línea base (404, `SIN_LINEA_BASE_CONGELADA`) y el tipo (404); bloquea `presupuesto_control` por `(linea_base_id, tipo_partida_id)` con `FOR UPDATE`; suma la venta del tipo; llama a `evaluar_captura_tope`; actualiza y asienta |
| `interfaz.py` (a) | Exporta `ContextoPresupuesto`, `LineaBaseMaterializada` y `materializar_importacion` | — |

### Infraestructura y esquema

| Objeto | Tipo | Detalle |
|---|---|---|
| `infraestructura/preparacion_json.py` (a) | función | `preparacion_desde_json(documento: Mapping[str, object]) -> Preparacion`. Lanza `FormatoPreparacionDesconocido(formato: object)` si `formato != 1` o falta una clave o un tipo no coincide. Las cifras se reconstruyen con el tipo de `tipos_base` de su campo, desde la cadena; los `hallazgos` de cada análisis, `()`. Propiedad: `preparacion_desde_json(preparacion_a_json(p)) == p` con hallazgos vacíos |
| `infraestructura/tablas.py` (a) | tablas Core | `obra`, `tipo_partida`, `nivel`, `area`, `partida`, `concepto`, `partida_concepto`, `apu`, `apu_insumo`, `apu_cargo`, `linea_base`; en b, `linea_base_concepto`, `explosion_presupuesto`, `presupuesto_control`; `insumo` gana `id`, `tipo`, `activo` y `creado_en_importacion`. Solo columnas usadas, sin DDL |
| `infraestructura/repositorio_linea_base.py` (a) | repositorio | `bloquear_obra`, `lineas_base_de_obra`, `tipos_partida`, `insumos_registrados`, `borrar_jerarquia(obra_id)` (los nueve pasos), `version_siguiente`, `insertar_insumos`, `insertar_niveles`, `insertar_areas`, `insertar_partidas`, `insertar_conceptos`, `insertar_partidas_concepto`, `insertar_apus` (con sus insumos y cargos), `insertar_linea_base`, `confirmar_importacion` (`UPDATE … SET estado = 'CONFIRMADO'`). Inserciones con `insert(tabla)` y lista de diccionarios |
| `infraestructura/repositorio_linea_base.py` (b) | repositorio | Reparto por fila: **B2** escribe `leer_linea_base`, `bloquear_linea_base`, `filas_explotables`, `copiar_conceptos`, `insertar_explosion`, `insertar_controles`, `congelar` y `activar_obra`; **B3** escribe `importes_venta_por_tipo`, porque `por_tipo_partida` es obligatorio en `LineaBase` y la respuesta del congelado lo necesita; **B4** escribe las lecturas paginadas de conceptos y explosión y la de la obra. Detalle: `filas_explotables(obra_id)` (une `partida_concepto`, `concepto`, `partida`, `apu`, `apu_insumo`, `insumo` y `apu_cargo`, en orden de `nivel.orden`, `area.id`, `partida.orden`, `concepto.codigo`), `copiar_conceptos(linea_base_id, obra_id)` (un `INSERT … SELECT gen_random_uuid(), …`), `insertar_explosion`, `insertar_controles` (una fila por cada fila de `tipo_partida`, sugerido de la explosión o `0.0000`, tope nulo), `congelar(linea_base_id, ahora, usuario_id, motivo)`, `activar_obra(obra_id, ahora, usuario_id)` (fija también `actualizado_en` y `actualizado_por_id`), `importes_venta_por_tipo(linea_base_id)` (suma de las copias si `CONGELADA`, de `partida_concepto` de la obra si `BORRADOR`; las cuatro filas de `tipo_partida` ordenadas por `id`, con `0.0000` donde no hay conceptos), y las lecturas paginadas |
| `infraestructura/repositorio_linea_base.py` (c) | repositorio | `bloquear_control(linea_base_id, tipo_partida_id)`, `actualizar_tope(…)`, `controles(linea_base_id)` |
| `area.tipo_unidad`, `apu.fecha_analisis`, `apu.analista`, `apu_cargo.porcentaje`, `apu_cargo.base_calculo` | columna | Pasan a admitir nulo |

**Migración `0011`** (`revision = "0011"`, `down_revision = "0010"`), tuplas `_SUBIDA` y `_BAJADA`, una sentencia por `op.execute`:

Subida: `ALTER TABLE area ALTER COLUMN tipo_unidad DROP NOT NULL`, y lo mismo para `apu.fecha_analisis`, `apu.analista`, `apu_cargo.porcentaje` y `apu_cargo.base_calculo`.

Bajada:

```sql
DO $guarda$
DECLARE
    con_nulos text[] := ARRAY[]::text[];
BEGIN
    LOCK TABLE area, apu, apu_cargo IN ACCESS EXCLUSIVE MODE;
    IF EXISTS (SELECT 1 FROM area WHERE tipo_unidad IS NULL) THEN con_nulos := con_nulos || 'area.tipo_unidad'::text; END IF;
    IF EXISTS (SELECT 1 FROM apu WHERE fecha_analisis IS NULL) THEN con_nulos := con_nulos || 'apu.fecha_analisis'::text; END IF;
    IF EXISTS (SELECT 1 FROM apu WHERE analista IS NULL) THEN con_nulos := con_nulos || 'apu.analista'::text; END IF;
    IF EXISTS (SELECT 1 FROM apu_cargo WHERE porcentaje IS NULL) THEN con_nulos := con_nulos || 'apu_cargo.porcentaje'::text; END IF;
    IF EXISTS (SELECT 1 FROM apu_cargo WHERE base_calculo IS NULL) THEN con_nulos := con_nulos || 'apu_cargo.base_calculo'::text; END IF;
    IF cardinality(con_nulos) > 0 THEN
        RAISE EXCEPTION USING MESSAGE = format(
            'La bajada de 0011 se niega: hay nulos en %s. El esquema de 0010 no los admite: '
            'rellena o retira esas filas fuera de esta migración, previo respaldo con pg_dump.',
            array_to_string(con_nulos, ', '));
    END IF;
END
$guarda$
```

seguida de los cinco `ALTER COLUMN … SET NOT NULL`.

**Migración:** `0011` — reversible: sí, sin nulos en esas columnas · destructiva: no · plan de reversa: con las columnas sin nulos, `alembic downgrade 0010` con el rol de migración deja el catálogo idéntico al de `0010` (`TC-A01`, incluido el nombre de las restricciones `NOT NULL` que PostgreSQL 18 registra: `E-4`). Con nulos se niega; como toda obra importada deja `area.tipo_unidad` nulo hasta la fase 2 (`PA-T17.11`), en la práctica la bajada exige retirar las obras importadas. `env.py` corre la cadena en una transacción: el rechazo deshace todo.

### API

Entra en TKT-017b la superficie de línea base y en TKT-017c la de control. Todas las rutas son `def`. Los importes salen con `serializar()` en campos `str`; las fechas, con zona.

| `operationId` · método y ruta | DTO entrada | DTO salida | Códigos y `tipo` de error | `x-roles` |
|---|---|---|---|---|
| `congelar_linea_base` · `POST /api/v1/lineas-base/{linea_base_id}/congelacion` (b) | `Motivo`: `motivo: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]` | `LineaBase` | `200` · `409 REGLA_NEGOCIO RN-01` · `409 CONFLICTO ESTADO_NO_PERMITE_OPERACION` · `409 CONCURRENCIA BLOQUEO_VENCIDO` · `422` · `403` · `404` | `DIRECTOR_PROYECTOS`; `verificar_origen` antes que `exigir_rol` |
| `listar_lineas_base` · `GET /api/v1/obras/{obra_id}/lineas-base` (b) | — | `list[LineaBase]`, versión descendente | `200` · `403` · `404` (obra) | `DIRECCION_GENERAL`, `DIRECTOR_PROYECTOS`, `COMPRAS` |
| `obtener_linea_base` · `GET /api/v1/lineas-base/{linea_base_id}` (b) | — | `LineaBase` | `200` · `403` · `404` | los tres |
| `listar_conceptos_linea_base` · `GET /api/v1/lineas-base/{linea_base_id}/conceptos` (b) | `tipo_partida_id: UUID \| None`, `nivel: str \| None` (igualdad con `nivel.nombre`), `q: str \| None` (`icontains(…, autoescape=True)` sobre código y descripción), `pagina ≥ 1 = 1`, `1 ≤ tamano_pagina ≤ 200 = 50` | `ListaConceptosLineaBase`, ordenada por `nivel.orden`, `area.nombre`, `partida.orden`, `concepto.codigo`, `linea_base_concepto.id`. Vacía en `BORRADOR` (`P-9`) | `200` · `422` · `403` · `404` | los tres |
| `obtener_explosion_insumos` · `GET /api/v1/lineas-base/{linea_base_id}/explosion` (b) | `tipo_partida_id: UUID \| None` | `ExplosionInsumos`; `importe_total` es la suma de los renglones devueltos; renglones vacíos en `BORRADOR` | `200` · `403` · `404` | los tres |
| `listar_presupuesto_control` · `GET /api/v1/lineas-base/{linea_base_id}/presupuesto-control` (c) | — | `list[PresupuestoControl]`, por `tipo_partida.id`; `[]` en `BORRADOR` (`P-9`) | `200` · `403` · `404` | los tres |
| `capturar_presupuesto_control` · `PUT /api/v1/lineas-base/{linea_base_id}/presupuesto-control/{tipo_partida_id}` (c) | `CapturaPresupuestoControl`: `importe_tope: Annotated[Dinero, PlainValidator(_importe_no_negativo)]` (rechaza con `ValueError` lo que no sea cadena con `^\d{1,14}(\.\d{1,4})?$`), `motivo: str \| None`, `confirmar_superior_a_venta: bool = False` | `PresupuestoControl` | `200` · `409 CONFLICTO TOPE_SUPERIOR_A_VENTA_SIN_CONFIRMAR` · `409 CONFLICTO SIN_LINEA_BASE_CONGELADA` · `409 CONCURRENCIA` · `422` · `403` · `404` | `DIRECCION_GENERAL`; `verificar_origen` antes que `exigir_rol` |

`congelada_por`, `capturado_por` y `actualizado_por` son `UsuarioResumen`, importado de `cimenta.identidad.interfaz`, con el nombre que da `nombres_de_usuarios`; son nulos solo cuando la columna del usuario es nula. La ruta `confirmar_importacion` no entra: es de TKT-018.

**Autorización por obra (IDOR).** Ninguna ruta de este ticket comprueba que quien llama esté asignado a la obra: el MVP no tiene ese eje de permiso. Lo dice la especificación de la API: «en el MVP no hay permiso por obra» (`docs/07-especificacion-api.md`, línea 399). La autorización es por rol, con `exigir_rol`.

**Cambios del borrador OpenAPI**, para el gate:

- (a) `ConfirmacionImportacion` añade `asignacion_tipos_partida`: `type: object`, `additionalProperties: {$ref: Uuid}`, obligatorio, con la descripción «Una entrada por nombre de partida leído; vale en todas las áreas donde aparece». El `requestBody` pasa a `required: true` (`P-1`). El `409` de `confirmar_importacion` deja de citar el fallo a mitad, que es `500`, y nombra `IMPORTACION_CON_ERRORES`, `REEMPLAZO_NO_CONFIRMADO` y `ESTADO_NO_PERMITE_OPERACION`.
- (b) `RenglonExplosion.importe_venta` → `importe_costo`, con la descripción «cantidad presupuestada × costo unitario» (`P-2`). `obtener_explosion_insumos` ya lleva `x-tickets: [TKT-016, TKT-017]`: la primera viñeta de `CA-B9` está cumplida y `TC-B16` lo fija. `congelar_linea_base` declara también el `409` `CONFLICTO` y el `CONCURRENCIA`.
- (c) La descripción de `listar_presupuesto_control` dice que devuelve `[]` en `BORRADOR` (`P-9`).

## Orden de implementación

Ciclo TDD de [metodología §16](../../metodologia.md#16--el-ciclo-tdd) por fila: el tester escribe en rojo los tests de la fila, el desarrollador los pone en verde de uno en uno y la verificación corre antes de la fila siguiente. Comandos desde `backend/` con Docker en marcha. Rojo válido: la función, el módulo o la ruta no existen, o el rechazo no ocurre; nunca un error de importación del propio test. `tester-backend` y `tester-api` van en `sonnet`, su valor por omisión.

**Número de la migración.** No está reservado (decisión «Coordinación con TKT-059» de `_index.md`). Al abrir A1, N es la cabeza de `Produccion` más uno, y N sustituye a `0011` (y la cabeza actual, a `0010`) en el nombre del archivo, `revision` y `down_revision`, el texto de la guarda, `TC-A01`, `TC-A02`, la constante `CABEZA` de `test_tkt072_migracion.py` y el `alembic heads` esperado de A0 y C0. En este documento, `0011` se lee como N. Si otro ticket fusiona antes una migración con el mismo número, la entrega que fusione segunda renumera antes de fusionar.

**Apertura y cierre de cada entrega.** Al abrir una entrega, si `Produccion` no cambió desde el cierre de la anterior, basta `uv run ruff check .`, `uv run mypy .`, `uv run lint-imports`, `uv run python -m herramientas.verificar_float` y `uv run alembic heads`; si cambió, también `uv run pytest -q -ra`. La suite completa y los tres comandos de documentación corren siempre en la fila de cierre de la entrega.

**Ejecución desde Cursor.** Si la entrega la ejecuta un agente de Cursor (`composer-2.5`), la columna Modelo no aplica: el modelo efectivo se anota en `impl.md`. Si Context7 no está disponible, valen las consultas ya registradas en «Estrategia». `/sdd-escalar` sí está disponible y es la salida de cualquier hueco del diseño. Ningún comando de este documento usa comodines de archivo: PowerShell no los expande al llamar a `uv run pytest`, así que los archivos se listan o se filtran con `-k`.

### TKT-017a · Materialización (entregas a1, a2 y a3; ramas en «Partición aprobada»)

| # | Paso | Tests que pone en verde | Agente | Modelo | Verificación | Estado |
|---|---|---|---|---|---|---|
| A0 | Línea base de herramientas y experimentos `E-1` a `E-4`. Sin código | — | `tester-backend` | `haiku` · tarea mecánica: comandos y resultado esperado escritos aquí | `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy .`, `uv run lint-imports`, `uv run python -m herramientas.verificar_float`, `uv run alembic heads` (la cabeza de `Produccion`, que fija N), `uv run pytest -q -ra`; desde la raíz, `python tools/verificar_docs.py`. Salida en `impl.md`. `E-3` es informativo: el tratamiento de los nulos ya está decidido (mapeo del análisis, decisión del 2026-11-06) | Pendiente |
| A1 | `v0011` con subida, bajada y guarda. El tester ajusta `test_tkt011_estructura.py`: las cinco tuplas de `TABLAS_DE_NULABILIDAD` pasan de `"no"` a `"sí"`, el valor que produce `_como_el_catalogo` (línea 173). Ajusta también `test_tkt072_migracion.py`, que hoy usa `REVISION_NUEVA = "0010"` (línea 33) para dos cosas distintas: se separa en `REVISION_0010 = "0010"`, que sigue siendo el paso de subida y bajada de `TC-18` (líneas 200 a 222) y el destino de `TC-21` (líneas 398 a 410), y `CABEZA = "0011"` (N; ver «Número de la migración»), que es la versión esperada antes y después del rechazo en `TC-20` (líneas 337 y 352) y en la bajada de `TC-21`. Sin ese cambio, la precondición de la línea 337 falla antes de llegar al rechazo, porque la base de prueba ya está en `0011`. El tester lleva a `conftest.py` el ayudante `esperar_hasta`, hoy duplicado en `test_tkt011_migracion_linea_base.py` (línea 350) y `test_tkt072_migracion.py` (línea 53), sin tocar esas dos copias: lo necesita el caso de bloqueo de `TC-A02`. ~45 líneas de producción, ~180 de pruebas | `TC-A01`, `TC-A02`, regresión de TKT-011 y TKT-072 ajustada | `tester-backend` → `desarrollador-sql` | `sonnet` · disparador: concurrencia (la guarda toma `LOCK TABLE` y el caso de bloqueo de `TC-A02` corre con dos sesiones) | `uv run pytest tests/test_tkt017_migracion.py tests/test_tkt011_estructura.py tests/test_tkt072_migracion.py -q` | Pendiente |
| A2 | `preparacion_desde_json` y `FormatoPreparacionDesconocido`. El tester crea `herramientas/soporte_tkt017.py` con `preparacion_sintetica()`: el libro de `CA-A1` (`620040-A` en dos áreas, precios de catálogo `414.93` y `428.19`, pie del análisis `420.0000`, insumo por crear `PANEL YESO 1/2`) con totales, costos, rendimientos y cargos completos en todos los insumos, también en los de mano de obra. No reutiliza `insumo_mano_obra` de `soporte_tkt016.py` (línea 102), que deja costo, rendimiento y cargo en `None`. ~120 y ~150 | `TC-A03` | `tester-backend` → `desarrollador-aplicacion` | `haiku` | `uv run pytest tests/test_tkt017_preparacion.py -q`; `uv run mypy .` | Pendiente |
| A2d | Documentación de a1: en `docs/03-modelo-datos.md` §4 y §11, la migración y las cinco columnas anulables, el precio unitario del pie del análisis y el ejemplo de `620040-A`; en `docs/glosario.md`, *Concepto de partida*. Sin código | `TC-A26` (parte de a1) | El orquestador, en el paso de documentación de `/sdd-ejecutar`, con `conv-documentacion` | — | Los tres comandos de documentación | Pendiente |
| A2c | Cierre de a1: mutantes `M-A8` y `M-A9`, uno a uno, revertidos | `TC-A01` a `TC-A03` | `tester-backend` | `sonnet` · valor por omisión | Cada mutante pone en rojo su test; tras revertir, los comandos de cierre de A8 | Pendiente |
| A3 | `dominio/explosion_materializada.py`. ~70 y ~120 | `TC-A09` | `tester-backend` → `desarrollador-dominio` | `sonnet` · disparador: regla de dinero (la explosión fija el sugerido que acompaña al tope de `RN-03`) | `uv run pytest tests/test_tkt017_explosion_materializada.py -q`; `uv run python -m herramientas.verificar_float`; `uv run lint-imports` | Pendiente |
| A4 | `dominio/materializacion.py`. El tester añade a `herramientas/soporte_tkt017.py`, que ya existe desde A2, las variantes de `TC-A04` a `TC-A08` y el ayudante `contar_filas_de_obra`. ~230 y ~330 | `TC-A04` a `TC-A08` | `tester-backend` → `desarrollador-dominio` | `sonnet` · disparador: regla de dinero (importe del concepto de partida e importe de venta) | `uv run pytest tests -q -k "tkt016 or tkt017_plan"`; `verificar_float`; `lint-imports` | Pendiente |
| A4c | Cierre de a2: mutantes `M-A2` y `M-A3`, uno a uno, revertidos | `TC-A04` a `TC-A09` | `tester-backend` | `sonnet` · valor por omisión | Cada mutante pone en rojo su test; tras revertir, los comandos de cierre de A8 | Pendiente |
| A5 | Al abrir a3, experimentos `E-6` y `E-7`. Después, `aplicacion/traduccion_motor.py`. Las pruebas provocan cada `SQLSTATE` real en una sesión del rol de aplicación y pasan el `DBAPIError` al traductor. ~80 y ~200 | `TC-A24` | `tester-backend` → `desarrollador-aplicacion` | `sonnet` · disparador: concurrencia (`55P03`) y disparador de inmutabilidad (`IN001`) | `uv run pytest tests/test_tkt017_traduccion.py -q` | Pendiente |
| A6a | `tablas.py`, `repositorio_linea_base.py` (parte a: lecturas, bloqueo de la obra e inserciones), `aplicacion/contexto.py`, `aplicacion/materializacion.py` con las precondiciones y el camino feliz, sin reemplazo, e `interfaz.py`. El tester añade `preparacion` a `DatosPresupuesto.importacion`. ~380 y ~400 | `TC-A10` a `TC-A17`, `TC-A19`, `TC-A20` | `tester-backend` → `desarrollador-aplicacion` | `sonnet` · disparador: bloqueo pesimista (`bloquear_obra`) | `uv run pytest tests/test_tkt017_materializacion.py -q`; `uv run lint-imports` | Pendiente |
| A6b | Reemplazo (`borrar_jerarquia`, `version_siguiente`, asiento `DESCARTAR` con la lectura del `CONFIRMAR`) y atomicidad. ~70 y ~150 | `TC-A18`, `TC-A21` | `tester-backend` → `desarrollador-aplicacion` | `sonnet` · disparador: bloqueo pesimista (borra bajo el bloqueo de la obra) | `uv run pytest tests/test_tkt017_materializacion.py -q` | Pendiente |
| A6c | Concurrencia. El tester añade a `conftest.py` la fixture `motor_espera_corta` (un `Engine` del rol de aplicación con `connect_args={"options": "-c lock_timeout=200ms"}`, `E-7`) y reutiliza `esperar_hasta`, que A1 ya llevó a `conftest.py`. ~15 de ajuste y ~200 | `TC-A22`, `TC-A23` | `tester-backend` → `desarrollador-aplicacion` | `sonnet` · disparador: concurrencia | `uv run pytest tests/test_tkt017_materializacion_concurrencia.py -q` **tres veces seguidas** sin intermitencia | Pendiente |
| A7 | Documentación de a3: ADR nuevo con su fila en el índice; conteo de ADR (contar `docs/adr/2*.md` después de crear el ADR y escribir esa cifra en `CLAUDE.md`, en los dos sitios de `README.md` y en `llms.txt`); el resto de las filas «a3» de «Documentación afectada». Sin código. ~150 | `TC-A26` | El orquestador, en el paso de documentación de `/sdd-ejecutar`, con `conv-documentacion` | — | Desde la raíz: `python tools/verificar_docs.py`, `python tools/extraer_mermaid.py`, `python -m unittest discover -s tools/tests -v` | Pendiente |
| A8 | Cierre de a3: mutantes `M-A1` y `M-A4` a `M-A7`, uno a uno, revertidos | Todos los de a y `TC-A25` | `tester-backend` | `sonnet` · valor por omisión | Cada mutante pone en rojo su test; tras revertir, `uv run ruff format --check .`, `uv run ruff check .`, `uv run mypy .`, `uv run lint-imports`, `verificar_float`, `uv run pytest -q -ra`, `python tools/verificar_escenarios.py`, los tres comandos de documentación. **Advertencia en `impl.md`:** `verificar_escenarios.py` no exige hoy ningún test de HDU-001, porque `tools/historias_activas.txt` la deja `PENDIENTE`; su verde no prueba la cobertura de escenarios de este ticket. La cobertura la prueba la tabla del plan de pruebas, y activar la historia es `P-13` | Pendiente |

**Tamaño de a:** ~1,015 líneas de producción, ~1,550 de pruebas y ~150 de documentación. Excede con claridad las ~400. **Partición (`P-10`, aprobada; filas exactas en la tabla siguiente):** a1 = A1 y A2 (~165, migración y deserializador); a2 = A3 y A4 (~300, dominio puro); a3 = A5 y A6 (~550, traductor, repositorio y caso de uso). a3 sigue por encima: el repositorio sin su caso de uso no tiene prueba de comportamiento, y el caso de uso sin el traductor deja `CA-A10` sin la salida `CONCURRENCIA`. A7 y A8 van con a3.

**Partición aprobada por la persona dueña el 2026-11-05 (`P-10`).** Seis entregas, cada una con su rama, su PR y su fusión, en este orden:

| Entrega | Filas | Rama |
|---|---|---|
| TKT-017a1 | A0, A1, A2, A2d y A2c | `tkt-017a1-migracion-y-preparacion` |
| TKT-017a2 | A3, A4 y A4c | `tkt-017a2-dominio-materializacion` |
| TKT-017a3 | A5, A6a, A6b, A6c, A7 y A8 | `tkt-017a3-materializacion` |
| TKT-017b1 | B0, B1, B2, B3, B3d y B3c | `tkt-017b1-congelado` |
| TKT-017b2 | B4, B5 y B6 | `tkt-017b2-lecturas-linea-base` |
| TKT-017c | C0 a C4 | `tkt-017c-presupuesto-control` |

Reglas de la partición, que la ejecución no reabre:

- Cada entrega abre según «Apertura y cierre de cada entrega» y cierra con su fila de cierre (A2c, A4c, A8, B3c, B6 y C4): la suite completa, los linters y los tres comandos de documentación de A8.
- Cada mutante se ejecuta en la entrega que contiene el código que muta: `M-A8` y `M-A9` en a1 (A2c); `M-A2` y `M-A3` en a2 (A4c); `M-A1` y `M-A4` a `M-A7` en a3 (A8); `M-B1` a `M-B8` en b1 (B3c); `M-B8` otra vez en b2 (B6), donde también lo matan las lecturas; `M-C1` a `M-C6` en c (C4). Ninguna entrega se fusiona con código suyo sin mutar.
- La documentación de cada entrega viaja con ella y la escribe el orquestador en el paso de documentación de `/sdd-ejecutar`, no un tester: A2d en a1, A7 en a3, B3d en b1, B5 en b2 y la parte documental de C4 en c. La columna «Entrega» de «Documentación afectada» dice qué va en cada una.

### TKT-017b · Congelado y lecturas (entregas b1 y b2; ramas en «Partición aprobada»)

| # | Paso | Tests que pone en verde | Agente | Modelo | Verificación | Estado |
|---|---|---|---|---|---|---|
| B0 | Apertura de b1 y experimentos `E-5`, `E-8` y `E-9`. Sin código | — | `tester-backend` | `haiku` · tarea mecánica | Lo esperado en cada experimento. **Si `E-5` falla, `/sdd-escalar` antes de B2** | Pendiente |
| B1 | `nombres_de_usuarios` y `UsuarioResumen` en `identidad` (`P-8`, aprobada; coordinada con TKT-059). Al abrir la fila se comprueban dos condiciones independientes: (a) si `cimenta.identidad.interfaz` no publica `nombres_de_usuarios(sesion_bd: Session, ids: Iterable[UUID]) -> dict[UUID, str]`, se escribe (repositorio, aplicación, `interfaz.py`); (b) si no publica `UsuarioResumen(BaseModel)` con `id: UUID` y `nombre: str`, se declara en `identidad/api/esquemas.py` y se publica en `interfaz.py`. El tester ajusta la lista cerrada de `__all__` de `test_tkt006_enrutador.py` (líneas 741 a 748) con lo que se cree. Si ambas existen ya, la fila queda hecha sin código y se anota en `impl.md`. ~40 y ~60 | `TC-B18` | `tester-backend` → `desarrollador-aplicacion` | `haiku` | `uv run pytest tests/test_tkt017_identidad_nombres.py tests/test_tkt006_enrutador.py -q`; `uv run lint-imports` | Pendiente |
| B2 | `repositorio_linea_base.py` (parte b, funciones de B2 según «Infraestructura y esquema») y `aplicacion/congelado.py`. ~280 y ~600 | `TC-B02`, `TC-B07` a `TC-B10`, `TC-B12`, `TC-B15` | `tester-backend` → `desarrollador-aplicacion` | `sonnet` · disparadores: inmutabilidad (escribe en las copias protegidas por el disparador) y bloqueo pesimista | `uv run pytest tests/test_tkt017_congelado.py tests/test_tkt017_congelado_concurrencia.py tests/test_tkt011_linea_base.py -q`, tres veces sin intermitencia | Pendiente |
| B3 | `importes_venta_por_tipo` en el repositorio; `api/esquemas.py` (`Motivo`, `LineaBase`, que importa `UsuarioResumen` de `cimenta.identidad.interfaz` para `congelada_por`), `api/rutas_linea_base.py` (congelación), `api/montaje.py`, `montar_presupuesto` en `servidor/fabrica.py`, y el docstring de `fabrica.py` (líneas 1 a 11), que pasa a decir que desde TKT-017b también monta `cimenta.presupuesto.api.montaje`. Después, `npm run tipos:generar` desde `frontend/` y se versiona `frontend/src/api/generado/servidor.ts`. ~200 y ~350 | `TC-B01`, `TC-B03` a `TC-B06`, `TC-B11`, `TC-B17`, `TC-B19` | `tester-api` → `desarrollador-api` | `sonnet` · disparador: los permisos de un rol (ruta exclusiva de `DIRECTOR_PROYECTOS`, con el `403` asentado como `DENEGAR`) | `uv run pytest tests/test_tkt017_api_congelado.py tests/test_tkt006_enrutador.py tests/test_tkt057_csrf.py -q`; desde `frontend/`, `npm run tipos:verificar` en verde con el archivo generado ya versionado (el trabajo de CI de `.github/workflows/ci.yml`, línea 114) | Pendiente |
| B3d | Documentación de b1: en el borrador, las respuestas `409` de `congelar_linea_base`; `docs/03-modelo-datos.md` §4.2; HDU-001 esc. 18 (`PA-T17.4`); ficha de TKT-012 en `docs/05` (`PA-T17.8`). Sin código | `TC-B16` (parte de b1) | El orquestador, en el paso de documentación de `/sdd-ejecutar`, con `conv-documentacion` | — | Los tres comandos de documentación | Pendiente |
| B3c | Cierre de b1: mutantes `M-B1` a `M-B8`, uno a uno, revertidos | Todos los de b1 y `TC-A25` | `tester-backend` | `sonnet` · valor por omisión | Cada mutante pone en rojo su test (`M-B8` lo mata `TC-B01`); tras revertir, los comandos de cierre de A8 | Pendiente |
| B4 | `aplicacion/consulta_linea_base.py`, las lecturas paginadas de conceptos y explosión y la de la obra en el repositorio, las tres rutas `GET` de línea base y la de obra. Después, `npm run tipos:generar` y se versiona `servidor.ts`. ~300 y ~350 | `TC-B13`, `TC-B14`, `TC-B19` | `tester-api` → `desarrollador-api` | `sonnet` · disparador: los permisos de un rol. Las lecturas no tocan dinero ni límite, pero cada una restringe a tres roles y `TC-B14` exige el `403` sin importes para los otros tres: es el mismo disparador que B3, y bajarla a `haiku` dejaría la única fila de lecturas con permisos por debajo del criterio aplicado a las demás | `uv run pytest tests/test_tkt017_api_lecturas.py tests/test_tkt006_enrutador.py tests/test_tkt057_csrf.py -q`; desde `frontend/`, `npm run tipos:verificar` | Pendiente |
| B5 | Documentación de b2: `importe_costo` en el borrador y `sdd/tickets/tkt-016/spec.md` (`PA-16.7`). Sin código. ~40 | `TC-B16` | El orquestador, en el paso de documentación de `/sdd-ejecutar`, con `conv-documentacion` | — | Los tres comandos de documentación | Pendiente |
| B6 | Cierre de b2: mutante `M-B8`, revertido | Todos los de b y `TC-A25` | `tester-backend` | `sonnet` · valor por omisión | `M-B8` pone en rojo `TC-B13`; tras revertir, los comandos de cierre de A8 | Pendiente |

**Tamaño de b:** ~830 de producción (~800 sin B1), ~1,700 de pruebas, ~80 de documentación. **Partición (`P-10`, aprobada):** b1 = B0 a B3c (~550, congelado de extremo a extremo); b2 = B4 a B6 (~300, lecturas). b1 sigue por encima por la misma razón que a3.

### TKT-017c · Presupuesto de control (entrega c; rama en «Partición aprobada»)

| # | Paso | Tests que pone en verde | Agente | Modelo | Verificación | Estado |
|---|---|---|---|---|---|---|
| C0 | Apertura de c. Sin código | — | `tester-backend` | `haiku` · tarea mecánica | Según «Apertura y cierre de cada entrega», con `alembic heads` en N, la migración de a1 | Pendiente |
| C1 | `dominio/captura_tope.py`. ~60 y ~120 | `TC-C18` | `tester-backend` → `desarrollador-dominio` | `sonnet` · disparador: regla de límite (`RN-03`) | `uv run pytest tests/test_tkt017_captura_tope.py -q`; `verificar_float` | Pendiente |
| C2 | `repositorio_linea_base.py` (parte c), `aplicacion/presupuesto_control.py`, `listar_presupuesto_control` en `consulta_linea_base.py`. ~180 y ~450 | `TC-C03`, `TC-C07` a `TC-C10`, `TC-C13`, `TC-C16`, `TC-C17` | `tester-backend` → `desarrollador-aplicacion` | `sonnet` · disparadores: regla de límite y bloqueo pesimista | `uv run pytest tests/test_tkt017_presupuesto_control.py -q`, tres veces sin intermitencia | Pendiente |
| C3 | `CapturaPresupuestoControl`, `PresupuestoControl` y `api/rutas_presupuesto_control.py`. Después, `npm run tipos:generar` y se versiona `servidor.ts`. El campo `importe_tope` (`Annotated[Dinero, PlainValidator(...)]`) tiene que salir en el esquema JSON como `type: string` con el patrón `^\d{1,14}(\.\d{1,4})?$`; un `PlainValidator` sin más deja el esquema vacío (`{}`), que el generador convierte en `unknown`. Si `TC-C19` lo encuentra vacío, se añade `WithJsonSchema({"type": "string", "pattern": "^\\d{1,14}(\\.\\d{1,4})?$"})` al `Annotated`. ~110 y ~350 | `TC-C01`, `TC-C02`, `TC-C04` a `TC-C06`, `TC-C11`, `TC-C12`, `TC-C14`, `TC-C15`, `TC-B19` (rutas de c), `TC-C19` | `tester-api` → `desarrollador-api` | `sonnet` · disparadores: regla de límite (`RN-03`: la ruta decide entre captura, recaptura y tope superior a la venta) y los permisos de un rol (exclusiva de `DIRECCION_GENERAL`, con `DENEGAR`) | `uv run pytest tests/test_tkt017_api_control.py tests/test_tkt006_enrutador.py tests/test_tkt057_csrf.py -q`; desde `frontend/`, `npm run tipos:verificar`, y en `servidor.ts` `importe_tope` es `string`, no `unknown` | Pendiente |
| C4 | Cierre de c: la documentación de c (la escribe el orquestador en el paso de documentación de `/sdd-ejecutar`), mutantes `M-C1` a `M-C6`, y HDU-001 pasa a activa en `tools/historias_activas.txt` (`P-13`) después de comprobar que todos sus escenarios tienen test | Todos y `TC-A25` | `tester-backend` | `sonnet` · valor por omisión | Igual que A8; con HDU-001 activa, `python tools/verificar_escenarios.py` en verde sin escenarios huérfanos. Si alguno de otro ticket queda sin test, `/sdd-escalar` en lugar de activar | Pendiente |

**Tamaño de c:** ~350 de producción, ~920 de pruebas. Dentro del límite.

**Modelo:** `haiku` por omisión; `sonnet` solo donde la fila cita su disparador de [metodología §14](../../metodologia.md#14--enrutamiento-de-modelo). Ninguna fila va en `opus`. B3, B4 y C3 subieron a `sonnet` por la objeción 10 de la pasada adversarial.

Estado: `Pendiente` · `✓ Hecho` · `⚠ Ajustado` (y el ajuste se documenta en `impl.md`).

## Experimentos previos

Ninguno se ha ejecutado. Cada uno lo corre la fila que se indica, antes de su rojo, y la salida va a `impl.md`. Por entrega: `E-1` a `E-4` al abrir a1 (A0); `E-6` y `E-7` al abrir a3 (A5); `E-5`, `E-8` y `E-9` al abrir b1 (B0).

| # | Afirmación | Cómo se comprueba | Fila | Si falla |
|---|---|---|---|---|
| `E-1` | La suite está en verde y la cabeza es `0010` | Los comandos de A0 | A0 | `/sdd-escalar` |
| `E-2` | `DELETE FROM linea_base_concepto WHERE false` con el rol de aplicación responde `42501` aunque no borre nada | `psql` o `psycopg` con el rol de aplicación contra la base migrada | A0 | Ninguno: confirma por qué el reemplazo no emite ese `DELETE` |
| `E-3` | Qué campos de un `AnalisisLeido` pueden quedar nulos en una preparación `VALIDADO`: totales, `costo_unitario`, `rendimiento` y `cargo` de los insumos de mano de obra, `tipo` e `importe` de los cargos | Leer `clasificacion_importacion.py` y analizar con `libro_sintetico` de TKT-015 un análisis sin esos valores; registrar el estado y la preparación | A0 | Informativo: cualquier nulo de esa lista ya se rechaza con `PreparacionInconsistente` (decisión del 2026-11-06) |
| `E-4` | En PostgreSQL 18, `DROP NOT NULL` y `SET NOT NULL` dejan la restricción `n` con el mismo nombre generado | `pg_constraint` de `area` antes y después del ciclo, con el rol de migración | A0 | `TC-A01` filtra `contype <> 'n'` y compara la nulabilidad por `information_schema.columns` |
| `E-5` | Dentro de la transacción que tiene la línea base con `FOR UPDATE`, el `INSERT … SELECT` en `linea_base_concepto` pasa el `FOR SHARE` de su disparador sin esperar | Una sesión del rol de aplicación: `SELECT … FOR UPDATE` de una línea base `BORRADOR` y luego el `INSERT … SELECT` | B0 | `/sdd-escalar` |
| `E-6` | `diag.constraint_name` vale `uq_linea_base_obra_id_congelada` en el `23505` del índice parcial y el nombre del disparador en `IN001`; `23001` llega a SQLAlchemy como `IntegrityError` y `55P03` como `OperationalError`, los dos subclase de `DBAPIError` | Provocar cada uno con el rol de aplicación por una `Session`. Que el borrado de un padre con hijos y `ON DELETE RESTRICT` responde `23001`, no `23503`, ya lo prueban `test_tkt011_linea_base.py` (líneas 1422 a 1441) y `test_tkt010_migracion.py` (línea 367); `E-6` solo confirma cómo lo envuelve SQLAlchemy | A5 | `/sdd-escalar` |
| `E-7` | `create_engine(motor_aplicacion.url, connect_args={"options": "-c lock_timeout=200ms"})` conecta con la contraseña del rol y `SHOW lock_timeout` devuelve `200ms` | Un test desechable | A5 | La fixture fija el valor con `SET lock_timeout` en un evento `connect` |
| `E-8` | `"   "` contra `StringConstraints(strip_whitespace=True, min_length=1)` produce `string_too_short` con `ctx.min_length == 1`, que el manejador traduce a `OBLIGATORIO` | Un modelo desechable y `codigo_de_error_pydantic` | B0 | `TC-B05` lo detecta; se cambia el DTO, no el manejador |
| `E-9` | `ColumnOperators.icontains(texto, autoescape=True)` existe en SQLAlchemy 2.1 y escapa `%` y `_` | Compilar la expresión contra el dialecto de PostgreSQL | B0 | `func.lower(…).like(…, escape="\\")` con escape explícito |

`SELECT … FOR UPDATE` sobre `presupuesto_control` y `explosion_presupuesto` con el rol de aplicación **ya está comprobado** por `tests/test_tkt011_permisos.py` (línea 252).

## Plan de pruebas

PostgreSQL real con testcontainers; esquema por `alembic upgrade head`; escrituras con el rol de aplicación. Los importes, desde cadena. Cada rechazo comprueba el contrato completo —`tipo`, `regla` o `codigo`, `detalle` con sus cifras como cadena y `acciones` filtradas por rol— y, después, que ninguna fila ni ningún asiento cambió (`contar_filas_de_obra`, ayudante del soporte que cuenta `nivel`, `area`, `partida`, `concepto`, `partida_concepto`, `apu`, `apu_insumo`, `apu_cargo`, `insumo`, `linea_base` y `bitacora`). En los casos de uso, el rechazo se comprueba con `excepcion.cuerpo(roles, "c")`.

### TKT-017a

| # | Caso | Tipo | Criterio que cubre | Escenario |
|---|---|---|---|---|
| TC-A01 | `test_tkt017_caa11_sube_y_baja_sin_nulos`: `base_vacia` a `0010`, fotografía A; `upgrade 0011`: las cinco columnas `is_nullable = 'YES'`; `downgrade 0010`: fotografía `== A`; `upgrade 0011` otra vez | feliz | `CA-A11` esc. 1 | — |
| TC-A02 | `test_tkt017_caa11_la_bajada_se_niega_con_nulos`, parametrizado por las cinco columnas: una fila con ese campo nulo; `downgrade 0010` → `P0001`, el texto nombra «La bajada de 0011 se niega» y la columna; versión y fotografía sin cambio. Caso de bloqueo: una sesión de aplicación inserta un `area` con `tipo_unidad` nulo sin confirmar; un hilo ejecuta la bajada y queda esperando (`esperar_hasta` con `pg_blocking_pids`); al confirmar la sesión, la bajada se niega con `P0001`. Este caso lleva `esperar_hasta` a `conftest.py`, porque es su primer uso en el ticket (A6c lo reutiliza) | **rechazo** | `CA-A11` esc. 2 | — |
| TC-A03 | `test_tkt017_caa05_preparacion_ida_y_vuelta` (la preparación de `preparacion_sintetica()` vuelve igual) y `test_tkt017_caa05_formato_desconocido`, parametrizado: `formato` 2, sin `formato`, `conceptos` no lista → `FormatoPreparacionDesconocido` | feliz y **rechazo** | `CA-A5` esc. 1, `CA-R1` | — |
| TC-A04 | `test_hdu001_esc11_el_plan_crea_un_concepto_con_dos_apariciones`: con la asignación `MUROS EXTERIORES` → MUROS y `PLAFON` → PLAFONES_Y_CAJILLOS, el plan tiene niveles con `orden` 1, 2 por fila, partidas con su tipo, un solo `620040-A`, dos apariciones a `420.0000` con importe `12.5000 × 420.0000 = 5250.0000` y `7.3333 × 420.0000 = 3079.9860`, el insumo `PANEL YESO 1/2` nuevo con `creado_en_importacion`, e `importe_venta` `8329.9860`. Variante con cantidad de Excel `7.33335`: se guarda `7.3334` y el importe es `7.3334 × 420.0000 = 3080.0280`, no `cuantizar(7.33335 × 420) = 3080.0070` | feliz | `CA-A1` | `HDU-001 esc. 11` |
| TC-A05 | `test_tkt017_caa03_asignacion_incompleta_o_inexistente`: sin `PLAFON` → `faltantes == ("PLAFON",)`; con un UUID ajeno → `inexistentes`; una clave sobrante se ignora | **rechazo** | `CA-A3` | — |
| TC-A06 | `test_tkt017_caa06_insumo_existente`: mismo código, unidad y tipo → reutiliza el `id`; otra unidad o tipo → `InsumoEnConflicto` con los dos lados | feliz y **rechazo** | `CA-A6` | — |
| TC-A07 | `test_tkt017_caa05_explosion_rechazada`, dos casos: cargos de utilidad e indirectos mayores que el precio en los conceptos de MUROS → `ExplosionRechazada` con una causa `SUGERIDO_NEGATIVO` cuyo `codigo_concepto` es `None` y cuyo `tipo_partida_id` es el de MUROS (causa por tipo); un análisis sin cargo de `UTILIDAD` → causa `CARGO_AUSENTE` con el código del concepto (causa por concepto) | **rechazo** | `CA-A5` esc. 2 | — |
| TC-A08 | `test_tkt017_caa05_preparacion_inconsistente`, parametrizado: concepto sin partida con nombre, sin descripción, código repetido en la misma partida, clave de insumo sin registro ni alta, `totales.material` nulo, insumo de mano de obra sin costo → `PreparacionInconsistente` con el código del concepto y, en los dos últimos, el nombre de la columna (`apu.costo_material`, `apu_insumo.costo_unitario`) | **rechazo** | `CA-A5` | — |
| TC-A09 | `test_tkt017_cab01_explotar_filas_es_determinista`: las mismas filas en otro orden dan la misma explosión; una fila sin análisis rechaza con `SIN_ANALISIS`; el resultado ya viene cuantizado | feliz y **rechazo** | `CA-B1` | — |
| TC-A10 | `test_hdu001_esc11_confirmar_materializa_la_jerarquia`: contra la base, todas las filas de TC-A04, la línea base `BORRADOR` versión 1, la importación `CONFIRMADO` y un asiento `CONFIRMAR` sin regla con `importacion_id` | feliz | `CA-A1` | `HDU-001 esc. 11` |
| TC-A11 | `test_hdu001_esc11_confirmar_con_errores_responde_importacion_con_errores` | **rechazo** | `CA-A2` esc. 1 | `HDU-001 esc. 11` |
| TC-A12 | `test_tkt017_caa02_otro_estado_de_importacion`, parametrizado `RECIBIDO`, `ANALIZANDO`, `CONFIRMADO`, `DESCARTADO` → `ESTADO_NO_PERMITE_OPERACION` con el estado en el detalle | **rechazo** | `CA-A2` esc. 2 | — |
| TC-A13 | `test_tkt017_caa03_asignacion_responde_422`: `OBLIGATORIO` en `asignacion_tipos_partida.PLAFON`; `VALOR_NO_PERMITIDO` con un tipo inexistente; la importación sigue `VALIDADO` | **rechazo** | `CA-A3` | — |
| TC-A14 | `test_tkt017_caa04_obra_que_no_admite_linea_base`: con congelada → mensaje y detalle de la vigente, la congelada intacta; obra `ACTIVA`, `SUSPENDIDA` o `CERRADA` sin congelada → `estado_obra` | **rechazo** | `CA-A4` | — |
| TC-A15 | `test_tkt017_caa05_formato_desconocido_no_escribe`: preparación con `formato` 2 en la base → `ESTADO_NO_PERMITE_OPERACION` con el mensaje de «analizarse de nuevo» | **rechazo** | `CA-A5` esc. 1 | — |
| TC-A16 | `test_tkt017_caa05_explosion_rechazada_no_escribe`, dos casos: con el sugerido negativo, el detalle trae `causas == [{"concepto": None, "causa": "SUGERIDO_NEGATIVO", "clave_insumo": None, "tipo_partida_id": "<id de MUROS>"}]`; con el cargo de utilidad ausente, `causas == [{"concepto": "<código>", "causa": "CARGO_AUSENTE", "clave_insumo": None, "tipo_partida_id": None}]`. Nada escrito | **rechazo** | `CA-A5` esc. 2 | — |
| TC-A17 | `test_tkt017_caa06_insumo_reutilizado_o_en_conflicto`: igual → un solo insumo y su marca intacta; distinto → `409` con los dos lados | feliz y **rechazo** | `CA-A6` | — |
| TC-A18 | `test_hdu001_esc12_fallo_a_mitad_no_deja_nada`: `monkeypatch` de `repositorio_linea_base.insertar_linea_base` con una función que lanza `RuntimeError("fallo provocado")` después de que ya se insertaron niveles y conceptos; el caso de uso propaga ese mismo `RuntimeError`, que no es `ErrorContrato`; cero filas nuevas, ningún asiento, la importación `VALIDADO` | **rechazo** | `CA-A7` | `HDU-001 esc. 12` |
| TC-A19 | `test_hdu001_esc13_reemplazo_sin_confirmar`: `REEMPLAZO_NO_CONFIRMADO` con `linea_base_borrador_id` y `version` 1; `cuerpo({"DIRECTOR_PROYECTOS"})` trae `CONFIRMAR_REEMPLAZO` con su ruta y `cuerpo({"COMPRAS"})` no; la jerarquía anterior intacta | **rechazo** | `CA-A8` esc. 1 | `HDU-001 esc. 13` |
| TC-A20 | `test_hdu001_esc13_reemplazo_sin_motivo`, parametrizado `None`, `""`, `"   "` → `422` `OBLIGATORIO` en `motivo_reemplazo` | **rechazo** | `CA-A8` esc. 2 | `HDU-001 esc. 13` |
| TC-A21 | `test_hdu001_esc13_reemplazo_confirmado`: con motivo «Corrección de cantidades del nivel 3», ninguna fila de la jerarquía anterior, insumos anteriores conservados, la nueva línea base versión 1, `DESCARTAR` con el motivo, sin regla, con versión e `importacion_id` de la anterior; `CONFIRMAR` de la nueva; la importación anterior sigue `CONFIRMADO` | feliz | `CA-A9` | `HDU-001 esc. 13` |
| TC-A22 | `test_tkt017_caa10_dos_confirmaciones_simultaneas`: dos hilos con `threading.Barrier`, dos importaciones `VALIDADO` de la misma obra; una termina, la otra `REEMPLAZO_NO_CONFIRMADO` o `ConcurrenciaVencida`; una sola línea base y todos los conceptos de una sola importación | concurrencia y **rechazo** | `CA-A10` | — |
| TC-A23 | `test_tkt017_caa10_la_confirmacion_espera_el_bloqueo_de_la_obra`: el hilo A se pausa dentro de `insertar_niveles` (envoltura con `threading.Event`); el hilo B confirma otra importación y queda en espera de A (`pg_blocking_pids` con `esperar_hasta`, sin espera fija). Variante con `motor_espera_corta`: B recibe `ConcurrenciaVencida` con `BLOQUEO_VENCIDO`, `excepcion.cabeceras() == {"Retry-After": "1"}`, `REINTENTAR` a la ruta de confirmación, y no escribe | concurrencia y **rechazo** | `CA-A10` | — |
| TC-A24 | `test_tkt017_cab06_traduccion_de_sqlstate`, parametrizado con errores reales: `IN001` (insertar una copia en una congelada) → `RN-01`; `23505` en `uq_linea_base_obra_id_congelada` → el rechazo de la vigente; `23505` en otra restricción → `ESTADO_NO_PERMITE_OPERACION`; `55P03` → `BLOQUEO_VENCIDO` con `excepcion.cabeceras() == {"Retry-After": "1"}`; `57014`, provocado con `SET LOCAL statement_timeout = '10ms'` seguido de `SELECT pg_sleep(1)`, → `TIEMPO_EJECUCION_VENCIDO` con `espera_maxima_ms` 15000 y la misma cabecera; `23503` (insertar una aparición con una partida inexistente) y `23001` (borrar un concepto que tiene apariciones) → `ESTADO_NO_PERMITE_OPERACION` con la restricción; `42501` y `22P02` → `None` | **rechazo** | `CA-B6` esc. 1 | — |
| TC-A25 | Regresión sin test nuevo: las suites de TKT-010, TKT-011, TKT-013 a TKT-016 y TKT-072 en verde; `lint-imports` en verde; `git diff --stat` en `backend/tests` solo toca los archivos ajustados que nombra cada fila | regresión de invariante | `CA-R1` | — |
| TC-A26 | Documentación coherente: los tres comandos de documentación en verde y cada fila de «Documentación afectada» de a aplicada | regresión | `CA-A12` | — |

### TKT-017b

| # | Caso | Tipo | Criterio que cubre | Escenario |
|---|---|---|---|---|
| TC-B01 | `test_hdu001_esc14_congelar_la_linea_base`: por la API, con 12 conceptos de partida de MUROS y PLAFONES_Y_CAJILLOS y el motivo «Firma de contrato 2026-11-04»: 12 copias con código, cantidad, precio e importe; la explosión; cuatro controles con el sugerido de la explosión, `0.0000` en ENCHAPES y GENERALES, tope nulo; `CONGELADA` con fecha, usuario y motivo; obra `ACTIVA`; `CONGELAR` con `RN-01`; `200` con la forma de `LineaBase`, con `congelada_por` como `UsuarioResumen` y `por_tipo_partida` con las cuatro filas. Después, la prueba modifica el importe de un `partida_concepto` de la obra (el rol de aplicación puede) y llama a `importes_venta_por_tipo` en una sesión propia, porque la ruta `obtener_linea_base` llega en b2: el resultado sigue siendo la suma de las copias, no la de `partida_concepto` | feliz | `CA-B1` | `HDU-001 esc. 14` |
| TC-B02 | `test_hdu001_esc14_la_explosion_congelada_es_la_validada`: tras confirmar y congelar, `planificar_materializacion` sobre la misma preparación y los insumos registrados da `plan.explosion`; sus renglones, por `(tipo_partida_id, codigo)`, son iguales a las filas de `explosion_presupuesto` unidas a `insumo`: cantidad, rendimiento congelado, costo e importe | feliz | `CA-B1`, invariante 19 | `HDU-001 esc. 14` |
| TC-B03 | `test_hdu001_esc19_segunda_linea_base_vigente`: `409` `REGLA_NEGOCIO` `RN-01`, detalle con `obra` «AP-058-25 · …», `linea_base_vigente_id` y `version_vigente` 1, mensaje de `SUPERSEDIDA`, `acciones` vacías; nada cambia | **rechazo** | `CA-B2` | `HDU-001 esc. 19` |
| TC-B04 | `test_tkt017_cab03_linea_base_u_obra_en_otro_estado`, parametrizado: línea base `CONGELADA` o `SUPERSEDIDA`; obra `SUSPENDIDA` o `CERRADA` | **rechazo** | `CA-B3` | — |
| TC-B05 | `test_tkt017_cab04_congelar_sin_motivo`, parametrizado sin campo, `""`, `"   "` → `422` `OBLIGATORIO` en `motivo`; sigue `BORRADOR` | **rechazo** | `CA-B4` esc. 1 | — |
| TC-B06 | `test_tkt017_cab04_congelar_sin_rol`, parametrizado `DIRECCION_GENERAL`, `COMPRAS` → `403` `PERMISO` `ROL_INSUFICIENTE`, sin `detalle`; un asiento `DENEGAR`; sigue `BORRADOR` | **rechazo** | `CA-B4` esc. 2 | — |
| TC-B07 | `test_hdu001_esc18_el_motor_rechaza_tocar_las_copias`: sobre las copias que dejó el congelado real, con el rol de aplicación: `INSERT` en las dos tablas y `UPDATE`/`DELETE` en `explosion_presupuesto` → `IN001`; `UPDATE`/`DELETE` en `linea_base_concepto` → `42501`; ninguna fila cambia; el `IN001` traducido es `409` `RN-01` | **rechazo** | `CA-B5` | `HDU-001 esc. 18` |
| TC-B08 | `test_tkt017_cab06_dos_congelados_simultaneos`: dos `BORRADOR` sembrados en la misma obra, dos hilos con `Barrier`; uno termina, el otro `RN-01` o `CONCURRENCIA`, nunca otra excepción; una sola `CONGELADA` | concurrencia y **rechazo** | `CA-B6` esc. 2 | — |
| TC-B09 | `test_tkt017_cab06_congelado_gana_al_reemplazo`: el congelado se pausa dentro de `copiar_conceptos`; la confirmación con reemplazo queda en espera (`pg_blocking_pids`); al liberar, la confirmación responde `ESTADO_NO_PERMITE_OPERACION` y la congelada conserva su jerarquía | concurrencia y **rechazo** | `CA-B6` esc. 3 | — |
| TC-B10 | `test_tkt017_cab06_reemplazo_gana_al_congelado`: la confirmación se pausa dentro de `insertar_niveles`; el congelado del borrador anterior queda en espera; al liberar, `NoEncontrado` `linea_base`; no queda ninguna congelada | concurrencia y **rechazo** | `CA-B6` esc. 3 | — |
| TC-B11 | `test_tkt017_cab06_congelado_con_bloqueo_vencido`: por la API, con la aplicación sobre `motor_espera_corta` y otra sesión con la obra bloqueada → `409` `CONCURRENCIA` `BLOQUEO_VENCIDO`, `Retry-After: 1`, `REINTENTAR` `POST` a la ruta de congelación; sigue `BORRADOR` | **rechazo** | `CA-B6` esc. 1 | — |
| TC-B12 | `test_tkt017_cab07_fallo_a_mitad_del_congelado`: `monkeypatch` de `insertar_controles` que lanza tras copiar; `BORRADOR` sin copias ni explosión ni controles, obra `PLANEACION`, sin `CONGELAR` | **rechazo** | `CA-B7` | — |
| TC-B13 | `test_hdu001_esc14_lecturas_de_la_linea_base`: las cuatro lecturas con los tres roles; formas del borrador; filtros por tipo, nivel y `q` (incluido un `q` con `%`, que no comodina); paginación con `total`; cadenas con cuatro y seis decimales; tras modificar el importe de un `partida_concepto` de una línea base congelada, `por_tipo_partida` sigue dando la suma de las copias | feliz | `CA-B8` esc. 1 | `HDU-001 esc. 14` |
| TC-B14 | `test_tkt017_cab08_lecturas_sin_rol_o_inexistentes`, parametrizado por las cuatro rutas y `RESIDENTE`, `ALMACEN`, `ADMINISTRACION` → `403` sin importes; obra o línea base inexistente → `404` `NO_ENCONTRADO` | **rechazo** | `CA-B8` esc. 2 | — |
| TC-B15 | `test_tkt017_cab01_explosion_imposible_al_congelar`: un `apu_cargo` del borrador corregido para que el sugerido sea negativo → `ESTADO_NO_PERMITE_OPERACION` con causas; nada cambia | **rechazo** | `CA-B1` | — |
| TC-B16 | El borrador: `obtener_explosion_insumos` con `TKT-017` en `x-tickets`; `RenglonExplosion` con `importe_costo` y sin `importe_venta`; `docs/03` describe `explosion_presupuesto.importe_venta` como cantidad × costo | regresión | `CA-B9` | — |
| TC-B17 | Los recorridos de rutas existentes cubren las rutas nuevas: `test_tkt006_enrutador.py` (ninguna `async def`, `GET` con `exigir_rol`) y `test_tkt057_csrf.py` (toda ruta que muta declara `verificar_origen` antes que `exigir_rol`) | regresión | `CA-R1` | — |
| TC-B18 | `test_tkt017_nombres_de_usuarios`: dos ids existentes y uno ajeno → solo los dos, con su nombre; `UsuarioResumen` publicado en `cimenta.identidad.interfaz` con exactamente `id` y `nombre` | feliz | `CA-B1` | — |
| TC-B19 | `test_tkt017_operation_id_de_las_rutas_de_presupuesto`, en el patrón de `TC-52` de `tests/test_tkt006_enrutador.py` (línea 503): el conjunto de `(método, ruta, operationId)` que publica la aplicación para `presupuesto` es exactamente el del borrador para las operaciones con `TKT-017` en `x-tickets` y ya implementadas. B3 lo crea con `congelar_linea_base`; B4 y C3 añaden las suyas a la lista esperada | regresión | `CA-B8`, `CA-R1` | — |

### TKT-017c

| # | Caso | Tipo | Criterio que cubre | Escenario |
|---|---|---|---|---|
| TC-C01 | `test_hdu001_esc15_consultar_las_cuatro_bolsas`: cuatro filas; importe de venta del tipo igual a la suma de los importes cuantizados de sus copias; suma de las cuatro igual a `linea_base.importe_venta`; tope nulo. Datos con redondeo: dos apariciones `0.0001 × 0.5000` cuantizadas a `0.0001` cada una, de modo que la suma de lo cuantizado (`0.0002`) difiere de cuantizar la suma (`0.0001`) | feliz | `CA-C1` esc. 1 | `HDU-001 esc. 15` |
| TC-C02 | `test_tkt017_cac01_consultar_sin_rol` → `403` sin importes | **rechazo** | `CA-C1` esc. 2 | — |
| TC-C03 | `test_hdu001_esc15_primera_captura`: venta `480000.0000`, sugerido `410000.0000`; captura `450000.0000` sin motivo; la fila con tope, `capturado_por_id` y `capturado_en`; sugerido intacto; `CREAR` sin regla; `consultar_bitacora(regla_negocio="RN-03")` no lo devuelve | feliz | `CA-C2` | `HDU-001 esc. 15` |
| TC-C04 | `test_hdu001_esc17_tope_superior_sin_confirmar`: `500000.0000` → `409` `TOPE_SUPERIOR_A_VENTA_SIN_CONFIRMAR`, detalle `MUROS`, `480000.0000`, `500000.0000`; `CONFIRMAR_TOPE_SUPERIOR` `PUT` a la misma ruta para `DIRECCION_GENERAL`; sin asiento | **rechazo** | `CA-C3` esc. 1 | `HDU-001 esc. 17` |
| TC-C05 | `test_hdu001_esc17_tope_igual_a_la_venta_no_pide_confirmacion`: `480000.0000` sin confirmar → `200` | borde | `CA-C3` | `HDU-001 esc. 17` |
| TC-C06 | `test_hdu001_esc17_confirmacion_sin_motivo` → `422` `OBLIGATORIO` en `motivo` | **rechazo** | `CA-C3` esc. 2 | `HDU-001 esc. 17` |
| TC-C07 | `test_hdu001_esc17_tope_superior_confirmado`: con «Subcontrato de bastidor más caro», tope `500000.0000`, motivo en la fila y en el asiento | feliz | `CA-C3` esc. 3 | `HDU-001 esc. 17` |
| TC-C08 | `test_hdu001_esc22_recaptura_del_tope`: `450000.0000` → `470000.0000` con motivo; `actualizado_*` y motivo en la fila; `RECAPTURAR` con `RN-03`, antes `450000.0000`, después `470000.0000`; aparece al consultar por `RN-03` | feliz | `CA-C4` esc. 1 | `HDU-001 esc. 22` |
| TC-C09 | `test_hdu001_esc22_bajar_el_tope_es_recaptura`: a `440000.0000` → `RECAPTURAR` `RN-03` con los dos valores | feliz | `CA-C4` esc. 2 | `HDU-001 esc. 22` |
| TC-C10 | `test_hdu001_esc22_mismo_valor_deja_otro_asiento` | feliz | `CA-C4` esc. 3 | `HDU-001 esc. 22` |
| TC-C11 | `test_hdu001_esc23_recaptura_sin_autoridad`: Director de Proyectos → `403`, `DENEGAR`, tope en `450000.0000` | **rechazo** | `CA-C5` esc. 1 | `HDU-001 esc. 23` |
| TC-C12 | `test_hdu001_esc23_recaptura_sin_motivo` → `422` `OBLIGATORIO`; tope intacto; ningún `RECAPTURAR` | **rechazo** | `CA-C5` esc. 2 | `HDU-001 esc. 23` |
| TC-C13 | `test_tkt017_cac06_linea_base_en_borrador` → `SIN_LINEA_BASE_CONGELADA` con el estado | **rechazo** | `CA-C6` esc. 1 | — |
| TC-C14 | `test_tkt017_cac06_tope_mal_formado`, parametrizado `"-1.0000"`, `"1.12345"`, `450000` (número), `"abc"` → `422` `FORMATO` en `importe_tope` | **rechazo** | `CA-C6` esc. 2 | — |
| TC-C15 | `test_tkt017_cac06_tipo_o_linea_base_inexistente` → `404` | **rechazo** | `CA-C6` esc. 3 | — |
| TC-C16 | `test_tkt017_cac07_recapturas_simultaneas`: dos hilos con `Barrier`, a `460000.0000` y `470000.0000`; dos `RECAPTURAR` y el `datos_antes` del segundo es el `datos_despues` del primero | concurrencia | `CA-C7` esc. 1 | — |
| TC-C17 | `test_tkt017_cac07_recaptura_espera_el_bloqueo`: una sesión tiene la fila con `FOR UPDATE`; la recaptura queda en espera (`pg_blocking_pids`); con `motor_espera_corta`, `BLOQUEO_VENCIDO` con `REINTENTAR` `PUT` y ningún asiento | concurrencia y **rechazo** | `CA-C7` esc. 2 | — |
| TC-C18 | `test_tkt017_cac03_evaluar_captura_tope`, pura: primera, recaptura, superior sin confirmar, superior confirmado sin motivo, igual a la venta, motivo en blanco | feliz, **rechazo** y borde | `CA-C2` a `CA-C5` | — |
| TC-C19 | `test_tkt017_cac06_importe_tope_se_publica_como_cadena`: en el `/openapi.json` de la aplicación, el esquema de `CapturaPresupuestoControl.importe_tope` tiene `type: string` y el patrón del borrador, no un esquema vacío | regresión | `CA-C6` | — |

**Concurrencia:** `TC-A22`, `TC-A23`, `TC-B08` a `TC-B11`, `TC-C16`, `TC-C17`. Las de pausa usan `threading.Event` con un tope de espera de 10 s que falla el test, nunca `sleep`.

### Mutación

La hace `tester-backend` en la fila de cierre de cada entrega, según el reparto de «Partición aprobada» (A2c, A4c, A8, B3c, B6 y C4): un mutante a la vez, revertido antes del siguiente; en `impl.md`, qué se mutó y qué test cayó.

| # | Mutante | Test que debe ponerse rojo |
|---|---|---|
| M-A8 | Quitar el `LOCK TABLE area, apu, apu_cargo IN ACCESS EXCLUSIVE MODE` de la guarda de la bajada | `TC-A02`, en su caso con una sesión que inserta un nulo sin confirmar mientras la bajada corre (la bajada debe esperar y, al confirmar la sesión, negarse) |
| M-A9 | `preparacion_desde_json` acepta cualquier `formato` | `TC-A03` (caso `formato` 2) |
| M-A1 | Quitar el `with_for_update()` de `bloquear_obra` | `TC-A22` (dos borradores) y `TC-A23` |
| M-A2 | En el plan, precio unitario del concepto de partida = el del catálogo | `TC-A04`, `TC-A10` |
| M-A3 | Cuantizar el importe sin cuantizar antes la cantidad y el precio | La variante `7.33335` de `TC-A04` |
| M-A4 | Calcular la versión antes del borrado | `TC-A21` (versión 2 en lugar de 1) |
| M-A5 | Comprobar el estado de la obra antes que la congelada | `TC-A14` (mensaje) |
| M-A6 | Añadir `DELETE FROM linea_base_concepto WHERE linea_base_id = :borrador` a `borrar_jerarquia` | `TC-A21` (`42501` → `500`) |
| M-A7 | En el traductor, `23505` de cualquier restricción → `RN-01` | `TC-A24` |
| M-B1 | Quitar el bloqueo de la obra en `congelar_linea_base` | `TC-B09` (la confirmación no espera) |
| M-B2 | Guardar en `rendimiento_congelado` el rendimiento del primer concepto en lugar del ponderado | `TC-B02` |
| M-B3 | No pasar la obra a `ACTIVA` | `TC-B01` |
| M-B4 | Asentar `CONGELAR` sin `RN-01` | `TC-B01` |
| M-B5 | `insertar_controles` solo para los tipos con conceptos | `TC-B01` (cuatro filas) |
| M-B6 | Comprobar la otra congelada después del estado de la obra | `TC-B03` |
| M-B7 | Quitar el `try/except DBAPIError` que llama al traductor en `congelar_linea_base` | `TC-B11` (`500` en lugar de `409` `CONCURRENCIA`) |
| M-B8 | `importes_venta_por_tipo` suma `partida_concepto` también cuando la línea base está `CONGELADA` | En b1, `TC-B01`; en b2, también `TC-B13`, en su caso que modifica el importe de un `partida_concepto` después del congelado (el rol de aplicación puede) y exige que `por_tipo_partida` siga dando la suma de las copias |
| M-C1 | `>` por `>=` en `evaluar_captura_tope` | `TC-C05`, `TC-C18` |
| M-C2 | Recaptura solo cuando el tope sube | `TC-C09` |
| M-C3 | `RECAPTURAR` sin `RN-03` | `TC-C08` |
| M-C4 | Quitar el `FOR UPDATE` de `bloquear_control` | `TC-C16`, `TC-C17` |
| M-C5 | Importe de venta del tipo = `ImportesTipoPartida.importe_venta` de la explosión (suma sin cuantizar por concepto) | `TC-C01` |
| M-C6 | Primera captura asentada con `RN-03` | `TC-C03` |

## Impacto

| Qué se toca | Quién depende | Riesgo | Mitigación |
|---|---|---|---|
| `0011` relaja cinco `NOT NULL` | Pruebas de estructura de TKT-011; bajadas desde la cabeza en TKT-072 | Las pruebas que esperan `"0010"` como cabeza fallan | A1 las ajusta y lo lista en `impl.md` |
| Bloqueo de la fila de `obra` | TKT-012 (máquina de estados de la obra), TKT-021 (requisición) | Un caso de uso futuro que bloquee la obra después de `presupuesto_control` invierte el orden | El ADR fija el orden importación → obra → línea base → control |
| `obra.estado` `PLANEACION` → `ACTIVA` escrito por `presupuesto` | TKT-012 (`PA-T17.8`) | TKT-012 modela la transición distinto | Nota en la ficha de TKT-012 en `docs/05` |
| `materializar_importacion` publicado | TKT-018 (ruta de confirmación y pantalla 3b) | Firma o campo de asignación distintos de lo que TKT-018 espera | `P-1`; el borrador queda actualizado en a |
| `RenglonExplosion.importe_venta` → `importe_costo` | TKT-018 (pantalla), tipos generados del cliente | Un cliente generado con el nombre viejo | No hay cliente que lo use todavía |
| `servidor/fabrica.py` monta `presupuesto` | Todas las pruebas que construyen la aplicación | Un fallo al montar rompe la suite de identidad | El montaje es perezoso, como el de identidad |
| `identidad.interfaz` gana `nombres_de_usuarios` y `UsuarioResumen` (`P-8`) | TKT-059 (fila 11), TKT-027 (bitácora con nombres), `test_tkt006_enrutador.py` (lista cerrada de `__all__`) | Que TKT-017b1 y TKT-059 los declaren dos veces | B1 comprueba al abrir si ya existen; quien los publica ajusta la lista de `__all__` |

### Omisiones señaladas por `revisor-impacto`

| # | Omisión | Estado |
|---|---|---|
| 1 | B3, B4 y C3 no regeneraban ni versionaban `frontend/src/api/generado/servidor.ts`, y `importe_tope` podía publicarse con esquema vacío | Incorporada: regeneración y `npm run tipos:verificar` en las tres filas, `TC-C19` y dos riesgos |
| 2 | `REVISION_NUEVA = "0010"` de `test_tkt072_migracion.py` mezcla la revisión con la cabeza, y la precondición de la línea 337 falla con `0011` | Incorporada en A1: `REVISION_0010` y `CABEZA` |
| 3 | Las tuplas de nulabilidad pasan a `"sí"`, no a `"yes"` | Incorporada en A1 |
| 4 | El conteo de ADR vive en cuatro sitios que `verificar_docs` no comprueba | Incorporada en «Documentación afectada» y en `P-11` |
| 5 | La ficha de TKT-017 en `docs/05` dice que la congelada anterior pasa a `SUPERSEDIDA` | Incorporada en «Documentación afectada» |
| 6 | La ficha de TKT-018 en `docs/05` no recibía el campo de asignación ni la firma de la materialización | Incorporada en «Documentación afectada» |
| 7 | `NoEncontrado` exige `mensaje` | Incorporada: tabla de mensajes de `NoEncontrado` |
| 8 | `verificar_escenarios.py` no exige nada mientras HDU-001 siga `PENDIENTE` | Incorporada: advertencia en A8, paso en C4 y `P-13` |
| 9 | El docstring de `servidor/fabrica.py` no decía que monta `presupuesto` | Incorporada en B3 |
| 10 | Ningún test fijaba los `operationId` de las rutas de presupuesto contra el borrador | Incorporada: `TC-B19` |

**Fronteras entre módulos:** No. `presupuesto` usa `auditoria` e `identidad` solo por su `interfaz.py`, las dos aristas ya están en el grafo, y no lee ninguna tabla ajena.

## Documentación afectada

| Entrega | Documento | Qué cambia |
|---|---|---|
| a3 | `docs/api/openapi.yaml` | `ConfirmacionImportacion` con `asignacion_tipos_partida`; `requestBody` obligatorio; descripción del `409` de `confirmar_importacion` |
| a1 | `docs/03-modelo-datos.md` §4 y §11 | Precio unitario del concepto de partida = pie del análisis; el del catálogo se descarta; ejemplo de `620040-A` reescrito; la migración y las cinco columnas anulables; la cuantización antes de calcular |
| a1 | `docs/glosario.md` | *Concepto de partida*: precio del pie del análisis |
| a3 | `docs/04-historias-usuario.md` | HDU-001 esc. 12: la importación nunca sale de `VALIDADO` |
| a3 | `docs/adr/20261105-preparacion-de-importacion-en-jsonb.md` | Un formato desconocido responde `ESTADO_NO_PERMITE_OPERACION` |
| a3 | `docs/adr/20261101-inmutabilidad-de-la-linea-base-en-el-motor.md` | Consecuencias: dónde vive la traducción y su tabla; `42501` sin traducción (`PA-T17.10`) |
| a3 | `sdd/tickets/tkt-014/spec.md` y `sdd/tickets/tkt-011/spec.md` | `PA-T13` y `PA-T17` resueltas el 2026-11-05 |
| a3 | ADR nuevo y su fila en `docs/adr/README.md` | Ver «¿Merece ADR?» |
| a3 | Conteo de ADR en `CLAUDE.md` (línea 14), `README.md` (líneas 30 y 264) y `llms.txt` (línea 27) | Se cuentan los archivos `docs/adr/2*.md` después de crear el ADR y esa cifra se escribe en los cuatro sitios: será 40 o 41 según llegue antes el ADR de TKT-059. `verificar_docs.py` no cuenta los ADR (líneas 201 a 211), así que nadie lo detectaría. La edición de `CLAUDE.md` está autorizada por `P-11` |
| a3 | `docs/05-tickets-trabajo.md`, ficha de TKT-017 | Se corrige la viñeta «La CONGELADA anterior pasa a SUPERSEDIDA…», que contradice el *Won't* de la spec y el esc. 19: este ticket no crea versiones nuevas sobre una congelada |
| a3 | `docs/05-tickets-trabajo.md`, ficha de TKT-018 (líneas 797 a 812) | Recibe el campo `asignacion_tipos_partida`, el `requestBody` obligatorio y la firma de `materializar_importacion`, que su ruta invoca |
| b1, b2 y c | `frontend/src/api/generado/servidor.ts` | Regenerado con `npm run tipos:generar` y versionado en B3, B4 y C3; `npm run tipos:verificar` lo comprueba en CI |
| b1 | `docs/api/openapi.yaml` | Respuestas `409` de `congelar_linea_base` |
| b2 | `docs/api/openapi.yaml` | `RenglonExplosion.importe_costo` |
| b1 | `docs/03-modelo-datos.md` §4.2 | `explosion_presupuesto.importe_venta` documentada como cantidad × costo unitario; el congelado crea las cuatro filas de control y pasa la obra a `ACTIVA` |
| b1 | `docs/04-historias-usuario.md` | HDU-001 esc. 18: el intento no se asienta (`PA-T17.4`) |
| b1 | `docs/05-tickets-trabajo.md` | Ficha de TKT-012: hereda `PLANEACION` → `ACTIVA` (`PA-T17.8`) |
| b2 | `sdd/tickets/tkt-016/spec.md` | `PA-16.7` resuelta |
| c | `docs/api/openapi.yaml` | `listar_presupuesto_control` devuelve `[]` en `BORRADOR` (`P-9`) |

## ¿Merece ADR?

**Sí, uno, en TKT-017a:** `docs/adr/20261105-ciclo-de-la-linea-base-serializado-por-la-obra.md`, formato MADR. Un recién llegado preguntaría por qué se bloquea la obra para confirmar un Excel. Opciones consideradas: bloqueo de la fila de `obra` (elegida); `pg_advisory_xact_lock` por obra; confiar solo en `uq_linea_base_obra_id_congelada` y traducir el `23505`; índice único parcial sobre `BORRADOR`; `SERIALIZABLE`. Se elige la primera porque es la única que serializa a la vez las dos confirmaciones (`CA-A10`) y el reemplazo frente al congelado (`CA-B6` esc. 3), con el `lock_timeout` del rol y un orden de adquisición fijo. Registra también la cuantización antes de calcular como consecuencia: la explosión congelada es, por construcción, la validada.

La traducción del motor no necesita ADR propio: ADR-031 ya la decidió; se amplían sus consecuencias.

## Pasada adversarial

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | El índice parcial sobre `CONGELADA` parece bastar para la concurrencia, y el bloqueo de la obra podría ser decoración | No basta: no hay unicidad sobre `BORRADOR` y el reemplazo borra filas que el congelado copiaría. `TC-A23`, `TC-B09` y `TC-B10` comprueban la **espera** con `pg_blocking_pids`, no solo el resultado, y `M-A1` y `M-B1` demuestran que caen sin el bloqueo |
| 2 | Alta | `CA-B1` pide la igualdad de dos explosiones calculadas sobre números distintos: la preparación trae los decimales del Excel y la base guarda la escala de su columna | Cuantización antes de calcular y una sola función, `explotar_filas` (`P-4`). `TC-B02` compara por insumo; `M-B2` la ataca |
| 3 | Alta | La clave de insumo de la preparación es la descripción normalizada, y el código del insumo registrado puede ser otro: las dos explosiones no agruparían igual | La explosión agrupa por el `codigo` del insumo resuelto, al confirmar y al congelar |
| 4 | Media | Un `DELETE` defensivo de las copias del borrador en el reemplazo parece prudente | Fallaría siempre con `42501` (`E-2`). Se prohíbe y `M-A6` lo vigila |
| 5 | Media | La comprobación de la congelada antes que el estado de la obra parece arbitraria | La exigen `CA-A4` esc. 1 y `CA-B2`: una obra con congelada ya está `ACTIVA`. `M-A5` y `M-B6` |
| 6 | Media | `23505` → `RN-01` sin mirar la restricción convertiría una carrera sobre `uq_insumo_codigo` en una violación de `RN-01` | Se restringe al índice de la vigente (`P-7`); `M-A7` |
| 7 | Media | La preparación puede traer nulos en columnas `NOT NULL` que `0011` no relaja; la escritura acabaría en `23502` y en `500` Resuelta por la persona dueña el 2026-11-06: mapeo fijo del análisis a `apu` y rechazo con `PreparacionInconsistente` de cualquier nulo en esas columnas; `TC-A08` cubre `totales.material` nulo y el insumo de mano de obra sin costo |
| 8 | Baja | Un mismo código con descripción o unidad distintas en dos áreas se resuelve con la primera aparición sin aviso | Lo deja pasar el análisis de TKT-015; queda como riesgo para TKT-018 con el archivo real (`PA-T17.9`) |
| 9 | Baja | `insertar_controles` crea una fila por cada `tipo_partida`; una base con tipos extra tendría más de cuatro | En todo despliegue la semilla `0008` deja exactamente cuatro; las pruebas de `CA-B1` no crean tipos con la fábrica |
| 10 | Media | Objeción del orquestador: B3 (ruta exclusiva de `DIRECTOR_PROYECTOS` con el `403` asentado) y C3 (regla de límite de `RN-03` y ruta exclusiva de `DIRECCION_GENERAL`) iban en `haiku`, y la tabla de disparadores de metodología §14 pide `sonnet` para una regla de límite y para los permisos de un rol | Incorporada: B3 y C3 suben a `sonnet` citando el disparador. B4 también sube: sus lecturas no tocan dinero, pero restringen por rol y exigen el `403` sin importes, que es el mismo disparador |
| 11 | Media | Revisión independiente del 2026-11-06: con `ON DELETE RESTRICT`, PostgreSQL respondería `23503` y no `23001`, así que la traducción y el orden de borrado deberían decir `23503` | No se aplica: es falso en este repositorio. `test_tkt011_linea_base.py` (líneas 1422 a 1441, `RestrictViolation`), `test_tkt010_migracion.py` (línea 367) y `test_tkt011_estructura.py` (línea 364) comprueban que el borrado de un padre con hijos responde `23001`, y `conv-sql-postgres` §9 lo registra. `23503` es el del hijo que apunta a un padre inexistente. La tabla de traducción ya cubre los dos |

## Riesgos

| Riesgo | Probabilidad | Impacto | Qué se hace |
|---|---|---|---|
| Un archivo real trae nulos en columnas del análisis que la migración no relaja | Media | Alto: esas importaciones se rechazan con «analizarse de nuevo» | Decidido el 2026-11-06: se rechazan. TKT-018 lo medirá con el archivo real (`PA-T17.9`) |
| Las pruebas de concurrencia salen intermitentes | Media | Medio | Pausas con `Event` y espera por `pg_blocking_pids`, nunca `sleep`; tres corridas seguidas en A6, B2 y C2 |
| a3 y b1 superan las ~400 líneas aunque se partan | Alta | Medio: revisiones largas | `P-10`; filas pequeñas dentro de cada una |
| El congelado de una obra grande se acerca al `statement_timeout` de 15 s | Baja | Medio | `E-13` de TKT-011 midió 5,000 copias y 300 renglones dentro del límite; la copia es un solo `INSERT … SELECT` |
| TKT-018 necesita otra forma de la asignación | Baja | Medio | `P-1` en el gate |
| `servidor.ts` queda sin regenerar tras B3, B4 o C3 | Media | Medio: falla `npm run tipos:verificar` en CI | La regeneración y la verificación están en la fila de cada ruta |
| `importe_tope` se publica con esquema vacío y el cliente lo tipa `unknown` | Media | Medio: el cliente perdería el tipo cadena del dinero | `TC-C19` y, si cae, `WithJsonSchema` explícito en C3 |

## Preguntas para el gate

| # | Pregunta | Recomendación |
|---|---|---|
| P-1 | Forma del campo de asignación en `ConfirmacionImportacion` | `asignacion_tipos_partida`: objeto `{nombre de partida: tipo_partida_id}`, obligatorio, con el `requestBody` obligatorio |
| P-2 | Nombre nuevo de `RenglonExplosion.importe_venta` (`PA-16.7`) | `importe_costo`. Descartados `importe` (ambiguo junto a `importe_total`) e `importe_material` (la fórmula no depende del tipo de insumo, aunque hoy solo explote materiales) |
| P-3 | Qué hacer si `E-3` muestra nulos en `apu.costo_*`, `total_cargos`, `precio_unitario`, en `apu_insumo.costo_unitario`, `rendimiento` o `cargo`, o en `apu_cargo.tipo` o `importe`; y cómo se llena `apu.total_indirectos`, que la preparación no trae | `total_indirectos` = suma de los importes de los cargos `INDIRECTOS`. Para los nulos, rechazar con `PreparacionInconsistente` («analizarse de nuevo») y no ampliar `0011` hasta ver el archivo real en TKT-018 |
| P-4 | Cuantizar cantidad, precios, rendimientos e importes de cargo a la escala de su columna antes de calcular importes y explosión | Sí: es la única forma de que lo validado sea lo congelado (`CA-B1`) |
| P-5 | De dónde sale la importación del borrador para el asiento `DESCARTAR` | Del asiento `CONFIRMAR`, asentado sobre la línea base, por `consultar_bitacora`. Alternativa: columna `linea_base.importacion_id` en `0011`, que amplía `A-M7` |
| P-6 | Extender la comprobación de `PA-T13` a todo insumo del análisis (unidad y tipo iguales a los registrados), rechazar la clave sin registro ni alta, y crear los insumos nuevos con `activo = true` | Sí a las tres |
| P-7 | La decisión «`23505` → `RN-01`» y `57014` | `RN-01` solo para `uq_linea_base_obra_id_congelada`; cualquier otro `23505` → `ESTADO_NO_PERMITE_OPERACION`; `57014` → `CONCURRENCIA` `TIEMPO_EJECUCION_VENCIDO` (`RNF-16`) |
| P-8 | El nombre de `congelada_por`, `capturado_por` y `actualizado_por` | Publicar `nombres_de_usuarios` en `cimenta.identidad.interfaz` (fila B1, ~30 líneas). Alternativa: omitir esos campos, que son opcionales, hasta TKT-027 |
| P-9 | Lecturas sobre un `BORRADOR` | Conceptos y explosión vacíos; `por_tipo_partida` desde `partida_concepto`; control `[]` |
| P-10 | Partir las entregas por tamaño | a → a1, a2, a3; b → b1, b2; c sin partir |
| P-11 | ADR nuevo y la edición del conteo de ADR, de 39 a 40, en `CLAUDE.md` (línea 14), `README.md` (líneas 30 y 264) y `llms.txt` (línea 27) | Sí a las dos; la edición de `CLAUDE.md` necesita la aprobación explícita de la persona dueña |
| P-12 | Claves de la asignación que no corresponden a ninguna partida | Ignorarlas: un nombre mal escrito ya produce el `422` del nombre que falta |
| P-13 | Activar HDU-001 en `tools/historias_activas.txt` para que `verificar_escenarios.py` exija un test por escenario | Sí, en la fila C4 de TKT-017c, cuando los escenarios 11 a 15, 17 a 19, 22 y 23 ya tengan test. Antes de ejecutarla, C4 lista los escenarios de HDU-001 que no son de este ticket (1 a 10 y los de TKT-018): si alguno no tiene test, la activación haría fallar el pipeline y se escala en lugar de activar |
