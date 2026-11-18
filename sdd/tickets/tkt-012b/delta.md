# Delta · TKT-012b · Mantenimiento y ciclo de vida de la obra

> [← index](_index.md) | [← impl](impl.md)

El delta no repite la implementación: declara **qué cambió en el sistema** respecto a como estaba antes. Es lo que leería alguien que no siguió el ticket.

El ticket se ejecutó en dos entregas dentro de una sola rama y un solo pull request. La **entrega a** (filas A1 a A9) aportó todo el backend: el verbo de bitácora `ELIMINAR`, el dominio del ciclo de vida y del historial, el repositorio, el puerto de historial, los casos de uso, las cinco rutas, el contrato y las pruebas de concurrencia y mutación. La **entrega b** (filas B1 a B6) aportó la pantalla «Obras» con sus acciones, la semilla de humo y la prueba de extremo a extremo. Las dos rondas de corrección de la revisión (`F001` y `F002a` de `auditor-arquitectura`, y los hallazgos de `auditor-seguridad`, `auditor-codigo` y `auditor-docs`) están registradas en `impl.md`.

## Añadido

| Qué | Dónde | Para qué |
|---|---|---|
| Migración `0017`: valor `ELIMINAR` en el tipo `accion_bitacora`, con bajada que se niega si existen asientos `ELIMINAR` | `backend/migraciones/versions/v0017_auditoria_verbo_eliminar.py` | La bitácora distingue el borrado físico de una obra de las demás acciones (`CANCELAR`, `ANULAR` y `DESCARTAR` significan otra cosa) |
| Máquina de estados de la obra: `evaluar_transicion`, `operaciones_admitidas`, `admite_edicion` y `cambios_efectivos` | `backend/cimenta/presupuesto/dominio/ciclo_vida_obra.py` | Reglas puras del ciclo de vida (`PLANEACION`, `ACTIVA`, `SUSPENDIDA`, `CERRADA`), sin framework |
| Función `hay_historial` y `ConteosHistorial` | `backend/cimenta/presupuesto/dominio/historial_obra.py` | Definición amplia de «historial» como regla de dominio, no escondida en una consulta |
| Puerto `FuenteHistorialObra` y campo `fuentes_historial` en `ContextoPresupuesto` | `backend/cimenta/presupuesto/aplicacion/historial_obra.py`, `contexto.py` | Que `presupuesto` cuente el historial de los módulos posteriores sin importarlos (ADR del 2026-11-17) |
| `FuenteHistorialArchivos`, publicada por `cimenta.archivos.interfaz` y cableada en `servidor/fabrica.py` | `backend/cimenta/archivos/infraestructura/fuente_historial.py` | Que una obra con archivos registrados no se borre y deje filas y objetos huérfanos |
| Casos de uso `actualizar_obra`, `eliminar_obra`, `suspender_obra`, `reactivar_obra` y `cerrar_obra`, con bloqueo `FOR UPDATE` de la obra | `backend/cimenta/presupuesto/aplicacion/mantenimiento_obras.py`, `ciclo_vida_obra.py` | Orquestar cada operación en una transacción con su asiento de bitácora |
| Repositorio de la obra: `bloquear_obra_completa`, `actualizar_obra`, `cambiar_estado_obra`, `eliminar_obra`, `contar_historial_propio` | `backend/cimenta/presupuesto/infraestructura/repositorio_obra.py` | Acceso a datos de las cinco operaciones |
| DTO `ObraCambios` y cinco rutas `def`: `PATCH` y `DELETE /obras/{obra_id}`, `POST …/suspension`, `…/reactivacion` y `…/cierre` | `backend/cimenta/presupuesto/api/esquemas.py`, `rutas_obras.py` | Exponer el mantenimiento y el ciclo de vida con CSRF y rol de alta |
| Ayudantes `traducir_fallo_de_obra`, `acciones_de_operaciones` y `ruta_de_operacion` | `backend/cimenta/presupuesto/aplicacion/traduccion_motor.py`, `ciclo_vida_obra.py` | Traducción única de los errores del motor y fuente única de las acciones del contrato |
| Opción `--congelar` de la semilla local | `backend/herramientas/semilla_linea_base_local.py` | Sembrar una obra `ACTIVA` con línea base congelada para el humo |
| Columna «Acciones», formulario de edición, motivo, confirmación de baja y bloqueo `OBRA_CON_HISTORIAL` | `frontend/src/modulos/presupuesto/obras/` (`PantallaObras.tsx`, `obras.acciones.ts`, `obras.consultas.ts`, `obras.formulario.ts`) | Operar las cinco acciones desde la interfaz |
| `fraccionAPorcentaje` y la opción `soloLectura` de `FormularioCatalogo` | `frontend/src/compartido/dinero/dinero.ts`, `compartido/formularios/FormularioCatalogo.tsx` | Precargar el porcentaje al editar y mostrar código y tipo de contrato sin permitir su edición |
| Aviso en línea opcional de `CapturaMotivo` y rótulos «Suspender» y «Cerrar» | `frontend/src/compartido/formularios/CapturaMotivo.tsx`, `compartido/componentes/bloqueo/etiquetas.ts` | Pintar el `409` de estado dentro del motivo y que el bloqueo no muestre la clave cruda |
| Dos pruebas E2E de `CA-18` y dos obras de mantenimiento sembradas | `frontend/e2e/obras.spec.ts`, `frontend/e2e/preparacion-global.ts` | Recorrer editar, suspender, reactivar y el bloqueo de eliminar contra el servidor real |
| Dos ADR | `docs/adr/20261117-verbo-eliminar-y-borrado-fisico-de-la-obra.md`, `docs/adr/20261117-historial-de-obra-por-puerto-inyectado.md` | Decisiones con opciones descartadas |
| Pruebas de la ficha | `backend/tests/test_tkt012b_*.py` (catorce archivos en total) y las de Vitest nuevas: las de `obras/`, `dinero.fraccion.test.ts`, `FormularioCatalogo.sololectura.test.tsx` y `etiquetas.acciones-obra.test.tsx` | Cobertura de `CA-1` a `CA-18` y `CA-R1` a `CA-R5` |

## Modificado

| Qué | Dónde | Antes → después |
|---|---|---|
| Verbos de bitácora | `backend/cimenta/auditoria/dominio/asiento.py`, `docs/03-modelo-datos.md` §10, `docs/api/openapi.yaml` | 23 verbos → 24, con `ELIMINAR` |
| Montaje de presupuesto | `backend/cimenta/presupuesto/api/montaje.py`, `servidor/fabrica.py` | Sin fuentes de historial → acepta `fuentes_historial`, y la fábrica pasa la de `archivos` |
| Pruebas existentes ampliadas por la decisión del ticket | `test_tkt007_dominio.py`, `test_tkt007_fronteras.py`, `test_tkt007_esquema.py`, `test_tkt029b_migracion.py`, `test_tkt029b_api_baja.py`, `test_tkt057_csrf.py`, `test_tkt017_api_congelado.py` | Aserciones de «23 verbos» → 24; `CUERPOS_VALIDOS` y `IMPLEMENTADAS_DE_PRESUPUESTO` con las cinco rutas nuevas. Todas declaradas en `impl.md` |
| `PantallaObras` | `frontend/src/modulos/presupuesto/obras/PantallaObras.tsx` | Solo alta y lista → alta, lista, edición y cuatro operaciones por fila. Los lectores siguen viendo exactamente Código, Nombre y Estado |
| Semilla de humo | `frontend/e2e/preparacion-global.ts` | Una obra con borrador → además dos obras de mantenimiento, una `ACTIVA` con línea base congelada y otra en `PLANEACION` con borrador |
| Wireframe «Obras» (2b) | `docs/08-wireframes.md` | Lista con alta → lista con columna «Acciones», edición, motivo, confirmación y bloqueo |
| Nota de arquitectura, especificación de la API y fila del backlog | `docs/02-arquitectura.md` §5, `docs/07-especificacion-api.md`, `docs/05-tickets-trabajo.md` | Documentan el puerto de historial, las cinco operaciones y la partición resuelta |
| Conteo de ADR | `CLAUDE.md`, `README.md`, `llms.txt` | 45 → 47 |
| Historias de usuario | `docs/04-historias-usuario.md` | Sin cambios: no se añadieron escenarios a HDU-001 y el escenario 20 no cambia |

## Eliminado

| Qué | Dónde | Por qué era seguro quitarlo |
|---|---|---|
| `ROLES_QUE_DAN_DE_ALTA` | `frontend/src/modulos/presupuesto/obras/PantallaObras.tsx` | Lo sustituye `ROLES_QUE_OPERAN`, que comparten la pantalla y `obras.acciones.ts`; los dos roles son los mismos |
| Las copias del callback `rechazo_vigente` y del mapa de acciones por operación | `aplicacion/mantenimiento_obras.py`, `ciclo_vida_obra.py` | Se unificaron en `traducir_fallo_de_obra` y `acciones_de_operaciones`; el comportamiento observable no cambió |

## Comportamiento observable nuevo

- Una persona con rol de Director de Proyectos o Dirección General puede **editar** el nombre, el domicilio, la retención de destajo, el fondo de garantía, el umbral de alerta y el IVA acreditable de una obra. El código, el tipo de contrato y el estado no se editan. Una obra `CERRADA` rechaza la edición.
- Esas mismas personas pueden **suspender**, **reactivar** y **cerrar** una obra con motivo obligatorio. Desde `PLANEACION` solo se ofrece cerrar; `CERRADA` es terminal. Cada operación deja su asiento de bitácora.
- Pueden **eliminar** una obra sin historial, y el borrado es físico y deja el asiento `ELIMINAR` con la fotografía de la obra. Una obra con historial (línea base de cualquier estado, importación, niveles, conceptos, precios, rendimientos observados o archivos) responde `409 OBRA_CON_HISTORIAL` con el detalle y las acciones que su estado permite.
- Dos operaciones simultáneas sobre la misma obra se serializan; un bloqueo agotado responde `409 CONCURRENCIA` con la acción `REINTENTAR`.
- Los demás roles ven la lista como antes, sin columna de acciones.

## Contrato público tocado

| Superficie | Cambio | ¿Rompe compatibilidad? |
|---|---|---|
| `PATCH /api/v1/obras/{obra_id}` (`actualizar_obra`) | Nuevo; cuerpo `ObraCambios` con `additionalProperties: false` | No |
| `DELETE /api/v1/obras/{obra_id}` (`eliminar_obra`) | Nuevo; `204`, `409 OBRA_CON_HISTORIAL`, `422` por identificador mal formado | No |
| `POST /api/v1/obras/{obra_id}/suspension`, `/reactivacion` y `/cierre` | Nuevos; cuerpo con `motivo`; `409 ESTADO_NO_PERMITE_OPERACION` con las operaciones admitidas | No |
| Enumeración `AccionBitacora` | Añade `ELIMINAR` | No, aunque un cliente con una enumeración cerrada debe regenerar los tipos |
| Código de conflicto `OBRA_CON_HISTORIAL` y sus acciones `SUSPENDER_OBRA` y `CERRAR_OBRA` | Ya estaban en el catálogo; ahora se emiten | No |
| `frontend/src/api/generado/servidor.ts` | Regenerado; `tipos:verificar` al día | No |
| Esquema de PostgreSQL | Sin tablas ni columnas nuevas; solo el valor de enumeración | No |

El PR toca `docs/api/openapi.yaml` y debe señalarse a quien apruebe.

## Decisiones (ADR)

### 2026-11-17 — El borrado de una obra es físico y lleva un verbo propio, `ELIMINAR`

**Contexto:** la obra se podía crear pero no eliminar, y la bitácora no tenía un verbo para el borrado.
**Opciones consideradas:** reutilizar `CANCELAR`, `ANULAR` o `DESCARTAR`; borrado lógico con una marca; borrado físico con verbo nuevo.
**Decisión:** borrado físico con el verbo nuevo `ELIMINAR`, solo si la obra no tiene historial.
**Evidencia:** [ADR del 2026-11-17](../../../docs/adr/20261117-verbo-eliminar-y-borrado-fisico-de-la-obra.md); `test_tkt012b_migracion.py` prueba la subida, la bajada con guarda y el uso del valor.
**Consecuencias:** la bajada de `0017` se niega si existen asientos `ELIMINAR`. El ADR no afirma el significado de `CANCELAR`, `ANULAR` y `DESCARTAR` en otros módulos; una persona debe confirmarlo en la revisión.

### 2026-11-17 — El historial de la obra se cuenta por un puerto inyectado desde la raíz de composición

**Contexto:** el borrado exige saber si hay filas de módulos posteriores, y `presupuesto` es el núcleo y no puede importarlos.
**Opciones consideradas:** importar `compras` (rompe el contrato `grafo-presupuesto`); ignorar los módulos posteriores; un puerto que `servidor/` rellena con las interfaces publicadas.
**Decisión:** el puerto `FuenteHistorialObra`, con la clave foránea `ON DELETE RESTRICT` como última barrera.
**Evidencia:** [ADR del 2026-11-17](../../../docs/adr/20261117-historial-de-obra-por-puerto-inyectado.md); `lint-imports` (16 contratos); la prueba de composición de extremo a extremo con `archivos`.
**Consecuencias:** cada módulo que escriba una tabla con `obra_id` debe publicar su fuente. `archivos` es la primera; `compras` y `almacén` quedan pendientes.

## Aprendizajes

| Aprendizaje | Evidencia | Dónde aplica |
|---|---|---|
| `SELECT … FOR UPDATE` sobre la fila de la obra bloquea el `INSERT` de una fila hija, y un `DELETE` con hijas responde `23001` (no `23503`) | Sondas del tester en A3 | Cualquier operación que deba serializarse contra la creación de hijas |
| Con un `LEFT OUTER JOIN`, PostgreSQL rechaza `FOR UPDATE` sobre el lado nulable: hay que acotarlo con `of=` a la tabla de la obra | A3; el SQL compilado lo muestra | Consultas que bloquean una fila con joins |
| El reloj se lee **después** de obtener el bloqueo, no antes; si no, un asiento puede quedar fechado antes del que lo precede | Ciclo de corrección 2, `auditor-codigo F005` y cuatro pruebas de concurrencia | Todo caso de uso con `FOR UPDATE` y asiento de bitácora |
| El detalle de un `409` no debe publicar nombres de restricciones ni otra estructura interna de la base | `auditor-seguridad F001` y la guarda parametrizada de 18 casos | Cualquier traducción de errores del motor |
| Ordenar asientos por `ocurrido_en, id` bajo un reloj fijo es aleatorio, porque el `id` es `uuid4`: las pruebas deben comparar el conjunto de acciones o avanzar el reloj | Dos pruebas intermitentes (A7 y la semilla de B5) | Pruebas de bitácora con el reloj de prueba |
| Con un diálogo modal abierto el resto de la página queda fuera del árbol de accesibilidad, así que las consultas por rol de la tabla deben usar `hidden: true` | TC-72 | Pruebas de componente con diálogos modales |
| `user-event` rechaza `clear()` sobre un elemento de solo lectura | B1 | Pruebas de campos `soloLectura` |
| Si dos auditores usan el mismo identificador, hay que citarlos con el prefijo del auditor | `auditor-sql F001` frente a `auditor-arquitectura F001` | Informes de revisión |

## Observaciones para `_evolucion.md`

| Tema | Observación | Severidad |
|---|---|---|
| `agente` | El diseño exigió a la vez que el esquema de edición no incluyera `codigo` ni `tipo_contrato` (TC-68) y que el formulario los mostrara de solo lectura (TC-70); lo destapó el rojo de B2 y se resolvió con un esquema de vista | Media |
| `comando` | El diseño afirmó que un conteo «usa los índices por `obra_id` que ya existen» sin comprobarlo en la base; `auditor-sql` encontró que es falso para tres tablas | Media |
| `agente` | Tres pruebas del tester nacieron defectuosas (un `clear()` sobre un campo de solo lectura, una consulta de tabla bajo un diálogo modal y dos con desempate aleatorio por `uuid4`) y el desarrollador, que no puede tocarlas, tuvo que devolverlas; se repite el patrón de TKT-029b | Media |
| `comando` | La auditoría de arquitectura encontró, al cerrar, una obligación del ADR del puerto ya vencida (`archivos` existía y el ADR decía que la fuente nacería con el primer módulo); la obligación debió figurar como fila del diseño | Alta |
| `comando` | Dos límites de uso de la cuenta interrumpieron tres auditorías y un tester en marcha; las tareas se reanudaron con el mismo contexto, pero conviene espaciar los despachos en paralelo | Baja |
| `plantilla` | El hub de un ticket partido no tiene una fila de Log por entrega cuando las dos se ejecutan seguidas en la misma sesión; el gate de `/sdd-completar` pide que conste cada una | Baja |

## Deuda que queda abierta

| Qué | Por qué se dejó | Ticket sugerido |
|---|---|---|
| **Índices por `obra_id`** en `precio_insumo`, `rendimiento_observado` y `solicitud_autorizacion` (migración aditiva `0018`). Sin ellos, el conteo del historial recorre las dos primeras enteras y la comprobación de la clave foránea del `DELETE` recorre las tres. `rendimiento_observado` crece con el avance. Condición de `auditor-sql`: el alcance completo, no solo el conteo | Amplía el alcance del ticket; la decide la persona dueña | Ticket de migración `0018` antes del primer dato real de avance |
| La máquina de estados de la obra no tiene `RN` en el PRD: solo la respaldan las decisiones D-2 y D-3 de la spec y `docs/03` §14 (`auditor-arquitectura F002b`) | Requiere decisión humana: añadir una `RN` o un ADR | Ticket de documentación del PRD |
| `traducir_error_del_motor` convierte `23505`, `23503`, `23001` genéricos y `22003` en `409 ESTADO_NO_PERMITE_OPERACION` en las operaciones de obra y conserva `detalle={"restriccion": …}` para otras operaciones (`auditor-arquitectura F003` y `auditor-seguridad F005`) | Lo comparten otros módulos | Ticket de endurecimiento del traductor |
| `eliminar_obra` no comprueba el estado: una obra `CERRADA` sin historial se borra por API aunque la pantalla solo ofrezca «Eliminar» en `PLANEACION` (`auditor-arquitectura F004`) | Pregunta abierta sin respuesta | Decisión de la persona dueña |
| El `409` por clave foránea lleva `movimientos: 1` como valor mínimo, no un conteo medido (`auditor-codigo N001`); falta decirlo en el borrador y en `docs/07` | Observación sin bloqueo | Mismo ticket que el traductor |
| `PantallaObras` tiene 474 líneas y mezcla lista, alta, edición, baja y motivo (`auditor-codigo F007`); el `as z.output<E>` de `FormularioCatalogo` sin justificar y sin prueba con casilla de solo lectura (O001); el `PATCH` envía siempre los seis campos y revierte ediciones ajenas (O002); `FuenteHistorialObra.nombre` solo lo lee un test (O003) | Refactores y observaciones diferidos por la persona dueña | Ticket de refactor de `PantallaObras` |
| El bloque `except` duplicado de `obras.py:219` (TKT-012a) | Fuera del alcance de este ticket | Ticket del traductor |
| **`code-review` (pasada previa al PR):** el botón «Reintentar» del bloqueo por concurrencia no hace nada en la pantalla de obras, porque `alAccion` solo atiende `VER_OBRA`, y el diálogo ya se cerró con lo tecleado; es el patrón del alta de TKT-012a, ahora alcanzable también desde edición, transiciones y baja | Defecto de interfaz heredado, sin prueba que lo cubra | Ticket de refactor de `PantallaObras` (junto a F007) |
| **`code-review`:** las cinco rutas releen la obra en otra transacción después de confirmar el cambio, así que la respuesta puede traer un estado posterior o un error con el cambio ya aplicado | Mismo patrón que el alta de TKT-012a | Ticket del traductor y del contrato de respuesta |
| `crear_importacion` (TKT-018) debe traducir el `23503` si el borrado de la obra gana la carrera, o responderá `500` al perder; los módulos `compras` y `almacén` deben publicar su fuente de historial | La ruta y los módulos aún no existen | TKT-018, TKT-030 y los de `almacén` |
| Los supuestos `(asumido)` pendientes de confirmar: que los archivos `PENDIENTE` y `CADUCADO` también cuentan como historial, que `fraccionAPorcentaje` devuelve `null` ante una entrada inválida y que los códigos de las obras del E2E llevan sufijo aleatorio por corrida. «Historial» como «existe alguna fila de `linea_base`» (D-DIS-5) es decisión aprobada por la persona dueña (`_index.md`) | La persona dueña debe confirmarlos | Revisión de la persona dueña |
| Las preguntas abiertas de las filas A5 y A7: no hay asignación usuario–obra; los asientos de las transiciones y de la edición ya no citan `RN-25` (resuelto) | Pregunta de producto | Decisión de la persona dueña |
| `pip-audit` no pudo ejecutarse sin red durante `auditor-seguridad`; las dependencias no cambiaron | Limitación del entorno | Lo ejecuta el pipeline del PR |
| `markdownlint-cli2` y `vale` se ejecutaron sobre los dos ADR (sin hallazgos); el diagrama `stateDiagram-v2` de `docs/03` se extrajo con `extraer_mermaid.py` pero no se vio en un navegador | Verificación visual pendiente | Revisión de la persona dueña |

## Pull request

**Título:** `TKT-012b · Mantenimiento y ciclo de vida de la obra`
**Origen:** `agent+human-review`: el código lo escribieron agentes y lo revisa una persona antes de fusionar.
**Cuerpo:** las cinco operaciones del borrador OpenAPI sobre la obra (editar, eliminar, suspender, reactivar y cerrar) con su máquina de estados, el verbo `ELIMINAR` de bitácora y el historial por puerto inyectado; la pantalla «Obras» con sus acciones; la semilla de humo y la prueba E2E de `CA-18`. Entrega a: backend (A1 a A9). Entrega b: pantalla, semilla, E2E y wireframe (B1 a B6). Se verifica con `uv run pytest`, `npm test`, `npm run e2e`, `lint-imports`, `tipos:verificar` y `python tools/verificar_docs.py`.

**Fusión con omisión:** la registrará el orquestador en un comentario del PR si se fusiona con omisión de la protección, con la aprobación explícita de la persona dueña.
