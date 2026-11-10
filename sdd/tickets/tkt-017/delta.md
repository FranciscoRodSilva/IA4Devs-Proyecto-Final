# Delta · TKT-017 · Confirmación y congelado de la línea base

> [← index](_index.md) | [← impl](impl.md)

El delta no repite la implementación: declara **qué cambió en el sistema** respecto a como estaba antes. El ticket se partió en seis entregas y este delta es **uno solo, del ticket entero**. Las dos primeras ya están en `Produccion`: TKT-017a1 ([PR #51](https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final/pull/51)) y TKT-017a2 ([PR #52](https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final/pull/52)). Las otras cuatro (TKT-017a3, TKT-017b1, TKT-017b2 y TKT-017c) se acumularon en la rama `tkt-017a3-materializacion` y salen en el único PR que abre `/sdd-completar`.

| Entrega | Qué aportó |
|---|---|
| TKT-017a1 | La migración `0011` (cinco columnas anulables con guarda en la bajada) y `preparacion_desde_json`, la inversa de `preparacion_a_json`, con el libro sintético de pruebas |
| TKT-017a2 | `explotar_filas` y `planificar_materializacion`: el dominio que convierte una preparación validada en el plan de filas de la línea base, con la explosión cuantizada, y sus rechazos tipados |
| TKT-017a3 | `materializar_importacion` (confirmar una importación `VALIDADO` y reemplazar el borrador), el traductor de errores del motor, el repositorio de la jerarquía y el ADR del ciclo de la línea base serializado por la obra |
| TKT-017b1 | El congelado de la línea base de extremo a extremo y su ruta `POST /api/v1/lineas-base/{id}/congelacion`, más `nombres_de_usuarios` y `UsuarioResumen` en `identidad` |
| TKT-017b2 | Las cuatro lecturas de la línea base (versiones de la obra, línea base, conceptos con filtros y paginación, explosión de insumos) |
| TKT-017c | El presupuesto de control: la regla de captura del tope, su caso de uso con bloqueo pesimista y bitácora, y las rutas `GET` y `PUT` de `presupuesto-control` |

## Añadido

| Qué | Dónde | Para qué |
|---|---|---|
| Migración `0011` | `backend/migraciones/versions/v0011_presupuesto_campos_sin_fuente.py` | Vuelve anulables `area.tipo_unidad`, `apu.fecha_analisis`, `apu.analista`, `apu_cargo.porcentaje` y `apu_cargo.base_calculo`, que la hoja puede traer vacíos. La bajada se niega si hay nulos |
| `preparacion_desde_json` y `FormatoPreparacionDesconocido` | `infraestructura/preparacion_json.py` | Leer la preparación que dejó el análisis; un formato desconocido, una clave ausente o un tipo inesperado se rechazan |
| `explotar_filas` y `planificar_materializacion`, con sus objetos de valor y rechazos | `dominio/explosion_materializada.py`, `dominio/materializacion.py` | Una sola función calcula la explosión al confirmar y al congelar: lo validado es exactamente lo congelado (invariante 19). Cuantiza a la escala de cada columna antes de calcular |
| `evaluar_importacion_confirmable`, `evaluar_confirmacion_en_obra`, `evaluar_congelado` y `evaluar_captura_tope` | `dominio/materializacion.py`, `dominio/congelado.py`, `dominio/captura_tope.py` | Las reglas de estado de la confirmación y del congelado (`RN-01`) y la decisión entre primera captura, recaptura y tope superior a la venta (`RN-03`, `RN-04`, `PA-03`) |
| `traducir_error_del_motor` | `aplicacion/traduccion_motor.py` | Convertir el `SQLSTATE` del motor en el contrato de error: `IN001` en `RN-01`, `23505` del índice de la vigente en el rechazo de la congelada, `55P03` en `BLOQUEO_VENCIDO`, `57014`, `22003`, `23503` y `23001` |
| `materializar_importacion`, `ContextoPresupuesto` y `construir_contexto` | `aplicacion/materializacion.py`, `aplicacion/contexto.py`, `interfaz.py` | Confirmar la importación: crea la jerarquía y la línea base `BORRADOR`, reemplaza un borrador anterior con motivo y asienta `CONFIRMAR` o `DESCARTAR` en la misma transacción |
| `congelar_linea_base` | `aplicacion/congelado.py` | Copiar los conceptos, guardar la explosión, crear las cuatro filas de control, pasar la línea base a `CONGELADA` y la obra a `ACTIVA`, y asentar `CONGELAR` con `RN-01` |
| `capturar_tope` y `ROLES_CAPTURA` | `aplicacion/presupuesto_control.py` | Capturar o recapturar el tope con `FOR UPDATE` sobre la fila de control y asiento `CREAR` o `RECAPTURAR` (`RN-03`) |
| Lecturas `listar_lineas_base`, `obtener_linea_base`, `listar_conceptos`, `obtener_explosion` y `listar_presupuesto_control` | `aplicacion/consulta_linea_base.py` | Entregar a la API datos ya leídos, con tipos propios de la capa; los importes de una congelada salen de las copias |
| Tablas Core y repositorio de la jerarquía, la línea base y el control | `infraestructura/tablas.py`, `infraestructura/repositorio_linea_base.py` | Leer y escribir la jerarquía, el bloqueo de la obra, el borrado en nueve pasos del reemplazo, las copias y el tope |
| `nombres_de_usuarios` y `UsuarioResumen` | `cimenta.identidad.interfaz` | Mostrar quién congeló y quién capturó sin que `presupuesto` lea la tabla `usuario` |
| Rutas y DTO de `presupuesto` | `api/esquemas.py`, `api/rutas_linea_base.py`, `api/rutas_presupuesto_control.py`, `api/montaje.py`; `montar_presupuesto` en `servidor/fabrica.py` | `POST` de congelación, cuatro `GET` de línea base, `GET` y `PUT` de `presupuesto-control` |
| ADR del ciclo de la línea base serializado por la obra | `docs/adr/20261105-ciclo-de-la-linea-base-serializado-por-la-obra.md` | Por qué confirmar, reemplazar y congelar se serializan con un bloqueo de la fila de `obra` (ver «Decisiones») |
| Pruebas | `backend/tests/test_tkt017_*.py`, `test_tkt057_csrf.py` ajustado | Cobertura de todos los criterios `[M]`; la suite pasa de 2146 (cierre de TKT-017a2, ya en `Produccion`) a 2677 casos |
| Soporte de pruebas | `backend/herramientas/soporte_tkt017*.py` | Libro sintético, entorno compartido, soporte de la API y siembra de una línea base congelada con cifras exactas |

## Modificado

| Qué | Dónde | Antes → después |
|---|---|---|
| Precio unitario del concepto de partida | `docs/03-modelo-datos.md` §4 y §11, `docs/glosario.md` | Salía del precio del catálogo → es el del pie del análisis (`PA-T17`); el importe es cantidad × ese precio, cuantizado; el glosario define además la *explosión de insumos* como `cantidad_concepto × rendimiento_insumo × costo unitario` |
| `ConfirmacionImportacion` | `docs/api/openapi.yaml` | Sin tipos de partida → `asignacion_tipos_partida` obligatorio y `requestBody` obligatorio; el `409` nombra `IMPORTACION_CON_ERRORES`, `REEMPLAZO_NO_CONFIRMADO` y `ESTADO_NO_PERMITE_OPERACION` |
| `RenglonExplosion` | `docs/api/openapi.yaml` | `importe_venta` → `importe_costo`, con su fórmula (`PA-16.7`) |
| Respuestas de `congelar_linea_base`, descripción de las lecturas y de `capturar_presupuesto_control` | `docs/api/openapi.yaml` | Se documentan los `409` de congelación, el comportamiento en `BORRADOR` y, para el `PUT`, `maxLength` y `NUL` del `motivo`, el `409` `CONCURRENCIA` y la respuesta |
| `detalle` del contrato de error | `contrato_error/excepciones.py` | No admitía `None` → admite `None` y lo conserva como `null` |
| HDU-001 esc. 12 y 18 | `docs/04-historias-usuario.md` | El esc. 12 decía que la importación pasaba a otro estado → «sigue en `VALIDADO`»; el esc. 18 pide el asiento del intento → no se asienta (`PA-T17.4`) |
| ADR de la preparación en JSONB y ADR de la inmutabilidad de la línea base | `docs/adr/` | Formato desconocido responde `ESTADO_NO_PERMITE_OPERACION`; tabla de `SQLSTATE` del traductor y la sustitución de la `CONGELADA` como versionado de `F1.6` |
| Conteo de ADR | `CLAUDE.md`, `README.md`, `llms.txt` | 39 → 40 (edición de `CLAUDE.md` autorizada por `P-11`) |
| Fichas de TKT-012, TKT-017 y TKT-018 | `docs/05-tickets-trabajo.md` | TKT-012 hereda `PLANEACION` → `ACTIVA`; TKT-017 deja de prometer una versión nueva sobre una congelada; TKT-018 recibe la asignación de tipos y la firma de la confirmación |
| `PA-T13`, `PA-T17`, `PA-16.7` | specs de TKT-011, TKT-014 y TKT-016 | Resueltas el 2026-11-05 y el 2026-11-10 |
| Pruebas de los recorridos existentes | `conftest.py`, `test_tkt057_csrf.py`, `test_tkt006_enrutador.py`, `test_tkt017_api_congelado.py` | `esperar_hasta` y `motor_espera_corta` como fixtures, y las rutas nuevas en los recorridos de CSRF y de `operationId`. Las de estructura y migración (`test_tkt011_estructura.py`, `test_tkt072_migracion.py`) las ajustó TKT-017a1 y ya están en `Produccion` |
| Cliente generado | `frontend/src/api/generado/servidor.ts` | Regenerado con las rutas de línea base y de control; `importe_tope` es `string` |
| Documentos y configuración menores | `docs/07-especificacion-api.md` (`x-tickets` de `/explosion`: solo TKT-017), `docs/08-wireframes.md` (esc. 12 de la pantalla 3b), `docs/03-modelo-datos.md` §4.2 (importe de la explosión y el congelado que crea el control), `backend/pyproject.toml` (`F811` en las pruebas de la API de TKT-017), `sdd/tickets/tkt-017/spec.md` (`RN-18` → `F1.6`) | Alineados con lo implementado |
| Regla «un solo PR por ticket, también partido en entregas» | `.claude/agents/git-entrega.md` (y su copia generada `.cursor/agents/git-entrega.md`), `.claude/skills/sdd-completar`, `sdd-disenar`, `sdd-ejecutar` y `sdd-revisar`, `sdd/metodologia.md`, `sdd/plantillas/_index.md` y `sdd/plantillas/delta.md`, `CLAUDE.md` | Una rama y un PR por entrega → entregas que solo dividen la ejecución y la revisión, un commit local por entrega y un único PR y un único delta al aprobarse la última (decisión de la persona dueña del 2026-11-09) |

## Eliminado

| Qué | Dónde | Por qué era seguro quitarlo |
|---|---|---|
| El precio por área del catálogo como origen del precio del concepto de partida | Diseño y glosario | `PA-T17` lo descarta: el del pie del análisis es el que valida la explosión. No hay código que lo usara |
| La rama de escalado de la fila A0 por nulos del análisis | `design.md` | La sustituye el mapeo fijo del análisis a `apu` con rechazo `PreparacionInconsistente` (decisión del 2026-11-06) |

## Comportamiento observable nuevo

- **Confirmar una importación** crea la jerarquía de la obra y su línea base en `BORRADOR`. Sin tipos de partida asignados, con errores bloqueantes, en otro estado, o en una obra con congelada o fuera de planeación, se rechaza con su contrato de error. Si ya hay un borrador, hay que confirmar el reemplazo con un motivo; el reemplazo conserva los insumos y asienta `DESCARTAR`.
- **Congelar** copia físicamente los conceptos y la explosión, crea el tope de control de los cuatro tipos de partida (con el sugerido de la explosión y el tope nulo), pasa la obra a `ACTIVA` y asienta `CONGELAR` con `RN-01`. Solo `DIRECTOR_PROYECTOS`. Una segunda congelada en la obra responde `409` `RN-01`.
- **Las lecturas de la línea base** (versiones, conceptos con filtros y paginación, explosión) están disponibles para `DIRECCION_GENERAL`, `DIRECTOR_PROYECTOS` y `COMPRAS`. Una congelada devuelve siempre lo copiado, aunque la jerarquía cambie.
- **El presupuesto de control**: Dirección General captura el tope de cada tipo de partida sobre una línea base congelada. La primera captura no exige motivo (`CREAR`, sin regla); la recaptura lo exige y se asienta `RECAPTURAR` con `RN-03`, con el valor anterior y el nuevo, también al bajar o repetir el valor. Un tope superior a la venta pide confirmar con motivo. Las recapturas simultáneas se encadenan.
- **Concurrencia**: confirmar, reemplazar, congelar y recapturar se serializan con bloqueos pesimistas; si vence la espera, `409` `CONCURRENCIA` con `Retry-After` y la acción `REINTENTAR`.
- **Entrada**: `importe_tope` solo acepta una cadena `^[0-9]{1,14}(\.[0-9]{1,4})?$`; el `motivo` no admite `NUL` ni más de 2000 caracteres; `confirmar_superior_a_venta` solo admite un booleano.

## Contrato público tocado

| Superficie | Cambio | ¿Rompe compatibilidad? |
|---|---|---|
| `POST /api/v1/lineas-base/{id}/congelacion` (`congelar_linea_base`) | Implementada | No: nueva; ya estaba en el borrador |
| `GET /api/v1/obras/{id}/lineas-base`, `GET /api/v1/lineas-base/{id}`, `GET …/conceptos` y `GET …/explosion` | Implementadas | No: nuevas |
| `GET` y `PUT /api/v1/lineas-base/{id}/presupuesto-control[/{tipo_partida_id}]` | Implementadas | No: nuevas |
| `POST /api/v1/importaciones/{id}/confirmacion` (`confirmar_importacion`) | Cuerpo con `asignacion_tipos_partida` obligatorio | Sí en el borrador, sin cliente que lo use: la ruta la implementa TKT-018 |
| `RenglonExplosion.importe_venta` → `importe_costo` | Renombrado | Sí en el borrador, sin cliente que lo use todavía |
| Tipos generados (`servidor.ts`) | Regenerados | No |
| Esquema PostgreSQL | Migración `0011`: cinco columnas pasan a admitir nulo | No: relajar un `NOT NULL` no rompe a quien escribe ni a quien lee |
| `cimenta.presupuesto.interfaz` | Publica `ContextoPresupuesto`, `LineaBaseMaterializada` y `materializar_importacion` | No: nuevos |
| `cimenta.identidad.interfaz` | Publica `nombres_de_usuarios` y `UsuarioResumen` | No: nuevos |
| Contrato de error | `detalle` admite valores `None` | No: amplía lo admitido |

**Aviso para quien apruebe el PR:** `docs/api/openapi.yaml` fue tocado en este PR.

## Decisiones (ADR)

### 2026-11-05 — El ciclo de la línea base se serializa con un bloqueo de la fila de `obra`

**Contexto:** confirmar un Excel, reemplazar el borrador y congelar compiten por la misma jerarquía. El índice único parcial sobre `CONGELADA` solo impide dos congeladas; no impide dos borradores ni que un congelado copie una jerarquía que otra sesión está borrando.

**Opciones consideradas:** el bloqueo `SELECT … FOR UPDATE` de la fila de `obra`; `pg_advisory_xact_lock` por obra; confiar solo en `uq_linea_base_obra_id_congelada` y traducir el `23505`; un índice único parcial sobre `BORRADOR`; `SERIALIZABLE`.

**Decisión:** el bloqueo de la fila de `obra`, siempre en el orden importación → obra → línea base → control, con el `lock_timeout` de 5 s del rol de aplicación. Es la única opción que serializa a la vez las dos confirmaciones y el reemplazo frente al congelado.

**Evidencia:** `test_tkt017_caa10_*` y `test_tkt017_cab06_*` comprueban la espera con `pg_blocking_pids` y los mutantes `M-A1` y `M-B1` caen sin el bloqueo.

**Consecuencias:** un caso de uso futuro que bloquee la obra en otro orden invertiría el bloqueo; el ADR lo fija. La cuantización antes de calcular queda registrada ahí como consecuencia: la explosión congelada es, por construcción, la validada.

→ [`docs/adr/20261105-ciclo-de-la-linea-base-serializado-por-la-obra.md`](../../../docs/adr/20261105-ciclo-de-la-linea-base-serializado-por-la-obra.md), con su fila en el índice. Lo creó TKT-017a3.

## Aprendizajes

| Aprendizaje | Evidencia | Dónde aplica |
|---|---|---|
| Un test que afirma con la misma fórmula que el código no prueba nada; los literales del criterio de aceptación sí | `TC-A04` (`5250.0000`, `3079.9860`, `8329.9860`, `3080.0280`) y `M-A2`, `M-A3` | Todo test de regla de dinero |
| Una regla que decide entre rechazos necesita su precedencia en un test propio, no solo cada rechazo por separado | `M-A5`, `M-B6`, `M-C1` y el test de precedencia de `captura_tope` | Reglas con varias causas (`RN-03`) |
| Un mutante que sobrevive en la suite de una entrega puede estar muerto en la de otra: anclarlo con un test en la entrega que lo introduce | `M-C5` lo mataba la suite de b y no la de c; `M-C14` no lo mataba nadie | Mutación en cierre de cada entrega |
| Un campo de texto libre que llega a `psycopg` necesita el rechazo del carácter `NUL` y un tope de longitud en el borde, o da un `500` | `Motivo` en b1 y `MotivoLibre` en c; el `motivo_reemplazo` de TKT-018 sigue expuesto | Todo texto libre de una ruta |
| `PlainValidator` con `WithJsonSchema` deja el esquema de `Dinero` como componente huérfano con `number`; una anotación propia con `__get_pydantic_core_schema__` y `__get_pydantic_json_schema__` no | `test_tkt017_cac06_el_contrato_publicado_no_trae_el_componente_dinero` | Todo campo de dinero en una entrada |
| `bool` de Pydantic en modo laxo acepta `"yes"` y `1`: un campo que confirma un límite debe ser `StrictBool` | `test_tkt017_cac06_confirmar_superior_a_venta_solo_admite_booleanos` | Campos de confirmación (`RN-03`) |
| El `FOR UPDATE` de la fila de control exige `UPDATE` al rol de aplicación, y `explosion_presupuesto` no puede tener la segunda barrera de `linea_base_concepto` | `test_tkt011_permisos.py` y el modelo de datos §4.2 | Tablas con bloqueo pesimista |
| La suite de concurrencia se comprueba esperando por `pg_blocking_pids`, no con `sleep`; una prueba de carrera por sí sola es probabilística frente al mutante | `TC-A23`, `TC-B09`, `TC-C17`; `TC-C16` | Todo bloqueo pesimista |

## Observaciones para `_evolucion.md`

| Tema | Observación | Severidad |
|---|---|---|
| `comando` | La regla de «un solo PR por ticket» llegó con a1 y a2 ya fusionadas: el ticket quedó con dos PR y un PR único, y hubo que registrar la excepción en el hub y repartir el delta del paraguas | Media |
| `guardrail` | El hub y `impl.md` de un paraguas de seis entregas crecieron hasta ~1,500 líneas de `impl.md`: cada comprobación de cifras (casos, `passed`) se desactualiza tras cada ciclo de corrección, y el auditor de docs abre un Menor por cada una. Falta que las secciones de cierre se generen con un comando, no a mano | Media |
| `agente` | Los auditores abrieron hallazgos de redacción en cada ciclo; el criterio de parada de `/sdd-revisar` (texto literal y sin reauditar) los cerró bien en b1, b2 y c | Baja |
| `agente` | El protocolo de mutación con copia fuera del repositorio y huella SHA-256 de todos los `.py` antes y después de cada mutante funcionó en a3, b1, b2 y c sin dejar ningún mutante en el árbol; conviene escribirlo en el agente `tester-backend` | Media |
| `plantilla` | La plantilla de `design.md` no tiene un campo para «mutantes añadidos en la ejecución»: `M-C7` a `M-C15` y las redefiniciones de `M-C5` no tenían dónde registrarse y el auditor de docs lo marcó | Media |
| `comando` | El diseño dejó una pregunta (`P-13`: activar HDU-001) cuya respuesta dependía de otros tickets; hubo que escalarla en el cierre de la última entrega. Conviene que la pregunta se haga al abrir el paraguas, con la lista de escenarios huérfanos | Media |
| `herramienta` | Archivos editados desde Windows llegaron al cierre en CRLF (cuatro de pruebas y `tablas.py`) y `git` avisa «CRLF will be replaced by LF»; el auditor de docs lo marcó. Una comprobación de finales de línea antes del cierre lo evitaría | Baja |

## Deuda que queda abierta

| Qué | Por qué se dejó | Ticket sugerido |
|---|---|---|
| Aprobar la confirmación en una ruta, con el motivo de reemplazo y la pantalla 3b | Es de TKT-018; TKT-017 deja `materializar_importacion` publicada | TKT-018 |
| `motivo_reemplazo` expuesto al `NUL` y sin tope de longitud (misma causa que `F001` de b1) | La ruta la construye TKT-018 | TKT-018: reutilizar `MotivoTexto` o equivalente |
| Medir el archivo real del catálogo (26 pruebas omitidas, `PA-T3`); nulos de columnas del análisis que `0011` no relaja; negativos en otras columnas con `CHECK` (`R-1`) | Dependen de variables de entorno y del archivo real | TKT-018 |
| Activar HDU-001 en `tools/historias_activas.txt` | Faltan test de los esc. 1, 2, 3, 16, 20, 21, 24, 25 y 26, de otros tickets; la persona dueña confirmó dejarla sin activar (`P-13`) | El ticket que cubra esos escenarios |
| Índice `ix_linea_base_concepto_partida_concepto_id` y `UNIQUE (concepto_id)` en `apu` | El `LEFT JOIN` de `filas_explotables` duplicaría apariciones con dos análisis por concepto | Migración de un ticket de esquema |
| `filas_explotables` e `importes_venta_por_tipo` filtran solo por `concepto.obra_id`; los `UPDATE` de `congelar` y `activar_obra` sin guardia de estado ni `rowcount` | Defensa en profundidad | Cuando se endurezca |
| La captura lee el estado de la línea base antes del bloqueo de la fila de control | Hoy es seguro: nada pasa una línea base a `SUPERSEDIDA` | El ticket que implemente `SUPERSEDIDA` (versionado de `F1.6`) |
| `traducir_error_del_motor` no traduce `23514` ni oculta `tabla` y `restriccion` en el `detalle` | Inalcanzable hoy por la API | Cuando se endurezca |
| `lineas_base_de_obra` ordena solo por `version DESC`; fixtures `base`, `entorno` y `contexto` repetidas en tres archivos de prueba | Fuera de las filas de c | Ticket de pruebas |
| El `PUT` de control relee la fila en otra transacción | Decisión del diseño; no hay fuga | Si se quiere exactitud, devolver la fila en la misma transacción |
| `max_length` de `q` y `nivel`; `MetaPagina.pagina` con enteros enormes; el `422` publicado como `HTTPValidationError` y sin `401`, `403` ni `404` | Sistémico | TKT-027 y TKT-061 |
| `soporte_tkt017_entorno.py` con `import pytest` a nivel de módulo; docstring de `identidad/api/montaje.py` al revés; `insertar_controles` sin guarda de lista vacía; `backend/.coverage` versionado; N+1 de `listar_lineas_base`; `conceptos_de_linea_base` ordena por el concepto vivo; el literal «La obra no existe.» repetido en `materializacion.py`; copias de `rutas_de` y `llamadas` en cuatro pruebas; `_rechazo_vigente` cae en `NoEncontrado(importacion)` si la congelada desaparece; mensaje de `22003` («analizarse de nuevo») impropio para el congelado | Hallazgos menores de las filas de a3, b1 y b2; ninguno alcanzable hoy | Ticket de despliegue, de pruebas o cuando se toque cada archivo (ver «Hallazgos fuera de alcance y deuda» de cada entrega en `impl.md`) |

## Pull request

**Título:** `TKT-017 · Confirmación y congelado de la línea base`

**Origen:** `agent`. El código lo escribieron los agentes en sesión de Claude (tester y desarrollador separados en cada fila); las decisiones D1 a D21 y las de la revisión son de la persona dueña, que no escribió el código.

**Cuerpo (resumen):**

- Cuatro entregas acumuladas en una sola rama: TKT-017a3 (confirmar y reemplazar el borrador, traductor del motor, ADR), TKT-017b1 (congelar y su ruta), TKT-017b2 (las cuatro lecturas) y TKT-017c (el presupuesto de control). TKT-017a1 y TKT-017a2 ya estaban en `Produccion` (PR #51 y #52).
- La explosión congelada es, por construcción, la validada (invariante 19); confirmar, reemplazar, congelar y recapturar se serializan con bloqueos pesimistas.
- Pruebas contra PostgreSQL real, con rechazo por regla y contrato de error completo; 2677 casos, mutantes `M-A1` a `M-C15`.
- Documentación: ADR nuevo (40 ADR), borrador OpenAPI, modelo de datos, historias y fichas.
- Cambia el toolkit: regla del PR único por ticket (`.claude/`, `.cursor/`, `sdd/metodologia.md` y plantillas).
- **Toca `docs/api/openapi.yaml`:** señalar a quien apruebe el PR.

**Cómo verificar:** `docker info`; desde `backend/` `uv run pytest -q`, `uv run ruff check .`, `uv run mypy .`, `uv run lint-imports`, `uv run python -m herramientas.verificar_float`; desde `frontend/` `npm run tipos:verificar`; desde la raíz `python tools/verificar_docs.py`.

**Fusión con omisión:** según la política del repositorio (`gh pr merge --admin`); el registro va en un comentario del PR tras la aprobación explícita de la persona dueña.
