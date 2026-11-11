# Delta · TKT-012a · Alta y consulta de obras

> [← index](_index.md) | [← impl](impl.md)

El delta no repite la implementación: declara **qué cambió en el sistema** respecto a como estaba antes. El ticket se ejecutó en dos entregas sobre una sola rama y este delta es **uno solo, del ticket entero**.

| Entrega | Qué aportó |
|---|---|
| TKT-012a-a (backend) | `crear_obra`, `listar_obras` y `obtener_obra` de punta a punta: la regla del rango de los porcentajes en `dominio/obra.py`, el repositorio de obra, el caso de uso con bitácora en la misma transacción y la traducción del `23505` de `uq_obra_codigo`, los tres endpoints y los tipos del cliente regenerados |
| TKT-012a-b (frontend y extremo a extremo) | La sección «Obras» del armazón, la pantalla con sus cuatro estados y el formulario de alta, `porcentajeAFraccion`, la casilla y el desplegable de `FormularioCatalogo`, el sembrador de humo parametrizado y la prueba de punta a punta del alta |

## Añadido

| Qué | Dónde | Para qué |
|---|---|---|
| `normalizar_codigo_obra`, `ParametroObra` y `porcentajes_fuera_de_rango` | `backend/cimenta/presupuesto/dominio/obra.py` | Recortar y pasar a mayúsculas el código de obra (`D-1`) y decidir el rango 0 a 1 de retención y fondo y el umbral no negativo (`PA-02`, `PA-18`) sin framework |
| Repositorio de obra (`FilaObraCompleta`, `empresas_activas`, `insertar_obra`, `leer_obra_completa`, `leer_obra_por_codigo`, `listar_obras`) | `backend/cimenta/presupuesto/infraestructura/repositorio_obra.py` | Leer y escribir `obra` con la línea base vigente, sin tocar el repositorio de línea base |
| Casos de uso `crear_obra`, `obtener_obra` y `listar_obras` | `backend/cimenta/presupuesto/aplicacion/obras.py` | Una transacción por alta con la bitácora `CREAR` dentro; el `23505` de `uq_obra_codigo` como árbitro del duplicado y de la carrera |
| Rutas `crear_obra`, `listar_obras` y `obtener_obra`, y los DTO `ObraNueva`, `Obra`, `ListaObras` y `EstadoObra` | `backend/cimenta/presupuesto/api/rutas_obras.py`, `api/esquemas.py` | Publicar el alta y la consulta de obras tal como las fija el borrador OpenAPI |
| Sección «Obras» y pantalla `PantallaObras` | `frontend/src/app/navegacion/secciones.ts`, `frontend/src/modulos/presupuesto/obras/` | Primera pantalla con datos reales: lista, botón `+` para Director de Proyectos y Dirección General, formulario de alta y conflicto de código duplicado en línea |
| `porcentajeAFraccion` | `frontend/src/compartido/dinero/dinero.ts` | Convertir «15» en `"0.150000"` con `decimal.js`, sin conversiones numéricas |
| `CIMENTA_HUMO_ROL`, `CIMENTA_HUMO_NOMBRE` y el usuario de humo `humo.director@cimenta.test` | `frontend/e2e/sembrar_usuario_humo.py`, `frontend/e2e/preparacion-global.ts` | Que la prueba de punta a punta inicie sesión como Director de Proyectos |
| Boceto «Obras» (§2b) | `docs/08-wireframes.md` | Documentar la pantalla y reconciliar el estado «Sin obras» del §2 |
| ADR «La unicidad del código de obra» | `docs/adr/20261110-unicidad-del-codigo-de-obra.md` | Registrar el índice único como árbitro, la traducción local del `23505` y las alternativas descartadas |

## Modificado

| Qué | Dónde | Antes → después |
|---|---|---|
| Modelo Core de `obra` y de `empresa` | `backend/cimenta/presupuesto/infraestructura/tablas.py` | Seis columnas de `obra` → las quince; sin tabla `empresa` → `empresa` con `id` y `activa`. Solo metadatos, sin DDL |
| `FormularioCatalogo` | `frontend/src/compartido/formularios/FormularioCatalogo.tsx` | Solo campos de texto, correo y fecha → además casilla y desplegable nativos; `CampoTexto` pasa a `CampoFormulario` |
| `etiquetas.ts` | `frontend/src/compartido/componentes/bloqueo/etiquetas.ts` | La acción `VER_OBRA` salía con su clave cruda → «Ver la obra»; `obra_existente` se muestra y `obra_existente_id` se oculta |
| `docs/api/openapi.yaml` | `ObraNueva` | Sin tope de longitud en `nombre` y `domicilio` → `maxLength` 200 y 500 (`D-5`) |
| `frontend/src/api/generado/servidor.ts` | tipos generados | Regenerado con las tres operaciones |
| Sembrador de humo | `frontend/e2e/sembrar_usuario_humo.py` | Rol y nombre fijos (`COMPRAS`, «Humo Compras») → leídos de `CIMENTA_HUMO_ROL` y `CIMENTA_HUMO_NOMBRE`, con los mismos valores por omisión; el `ON CONFLICT` también actualiza `nombre` |
| Pruebas de TKT-008, TKT-017 y TKT-057 | `secciones.test.ts`, `Armazon.test.tsx`, `FormularioCatalogo.test.tsx` (TC-86), `test_tkt017_api_congelado.py` (TC-B19), `test_tkt057_csrf.py` | Declaradas en `impl.md`: «Obras» al final de las listas, la etiqueta «Ver la obra», los tres `operationId` nuevos de `presupuesto` y el cuerpo válido de `POST /api/v1/obras`. Solo se amplía lo esperado, salvo TC-86, que decidió la persona dueña |
| `docs/05-tickets-trabajo.md`, `docs/07-especificacion-api.md`, `README.md`, `docs/arranque-local.md`, `CLAUDE.md`, `llms.txt` | documentación | Partición de TKT-012 en 012a y 012b, tickets de las filas de `/obras`, variables del sembrador, y el recuento de ADR de 40 a 41 |
| `docs/05-tickets-trabajo.md` (particiones de otros tickets) y `sdd/tickets/tkt-018a/`, `sdd/tickets/tkt-029a/` | documentación | Además de la partición de TKT-012 en 012a y 012b (`docs/05` ~628), el PR lleva las particiones de TKT-018 en 018a y 018b (~827) y de TKT-029 en 029a y 029b (~1115), con sus carpetas de planificación sin ejecutar. Ya estaban en el árbol de trabajo antes de este ticket y `docs/05` es un solo archivo: la persona dueña decidió el 2026-11-10 incluirlas en este PR |

## Eliminado

| Qué | Dónde | Por qué era seguro quitarlo |
|---|---|---|
| Ninguno | — | — |

## Comportamiento observable nuevo

- Un Director de Proyectos o la Dirección General puede dar de alta una obra con código, nombre, domicilio, tipo de contrato, retención de destajo, fondo de garantía, umbral de alerta opcional e IVA acreditable. La obra nace en `PLANEACION`; el código se guarda recortado y en mayúsculas.
- Un código repetido, también en minúsculas o con espacios, y dos altas simultáneas con el mismo código responden `409 CODIGO_OBRA_DUPLICADO` con la obra existente y la acción «Ver la obra».
- Un porcentaje fuera de 0 a 1, o un umbral negativo, responde `422 FUERA_DE_RANGO` por campo, antes de llegar al motor.
- Los seis roles ven la lista de obras y cada obra con su línea base vigente. Los roles distintos de Director de Proyectos y Dirección General no ven el botón `+`.
- El menú del armazón gana la entrada «Obras», en el grupo «Obra», que se muestra primero. Almacén y Residente de obra ven «Obras» como primera entrada del menú (antes, «Órdenes de compra»). La sección de entrada al armazón (`primeraSeccion`) no cambia.

## Contrato público tocado

| Superficie | Cambio | ¿Rompe compatibilidad? |
|---|---|---|
| `POST /api/v1/obras` (`crear_obra`) | Nueva: `201` con `Location`, `409 CODIGO_OBRA_DUPLICADO`, `422`, `403`, `401` | No |
| `GET /api/v1/obras` (`listar_obras`) | Nueva: `estado` repetible, `pagina`, `tamano_pagina`; página inalcanzable devuelve lista vacía | No |
| `GET /api/v1/obras/{obra_id}` (`obtener_obra`) | Nueva: `200`, `404 NO_ENCONTRADO` | No |
| `ObraNueva`, `Obra`, `ListaObras`, `EstadoObra` | Nuevos; `ObraNueva` lleva `maxLength` 200 y 500 en `nombre` y `domicilio`; `actualizado_en` se omite cuando no tiene valor | No |
| Tipos generados del cliente | `servidor.ts` regenerado | No |
| Esquema de base de datos | Sin cambio: ninguna migración | No |

## Decisiones (ADR)

### 2026-11-10 — El código de obra es único por `uq_obra_codigo` y el alta traduce su `23505`

**Contexto:** el alta tiene que rechazar el código repetido y resistir dos altas simultáneas con el mismo código.
**Opciones consideradas:** comprobación previa con `SELECT`; bloqueo consultivo; el índice único como único árbitro con traducción del `23505`; traducir en el módulo compartido de TKT-017 o localmente; rango por expresión regular del DTO o por función de dominio.
**Decisión:** índice único como árbitro, traducción local en `aplicacion/obras.py` y rango en una función pura de dominio.
**Evidencia:** TC-11, TC-12 (concurrencia determinista con `pg_blocking_pids`) y los mutantes `M-3` y `M-4`.
**Consecuencias:** la extracción de `sqlstate` y `constraint_name` queda duplicada con `traduccion_motor.py` y se desvía la consecuencia «la traducción vive en un solo punto» de ADR-031.

→ [`docs/adr/20261110-unicidad-del-codigo-de-obra.md`](../../../docs/adr/20261110-unicidad-del-codigo-de-obra.md), con su entrada en el índice.

## Aprendizajes

| Aprendizaje | Evidencia | Dónde aplica |
|---|---|---|
| Pydantic publica un `Literal` de un solo valor como `const`, sin `enum`; el borrador pide `enum` | TC-30 en rojo | Cualquier DTO con un valor único: `json_schema_extra={"enum": [...]}` |
| Para omitir de la respuesta un campo que el borrador declara no nulo, `response_model_exclude_unset` y asignarlo solo si hay valor; los campos nulables siguen saliendo como `null` | TC-14, TC-30 | Cualquier DTO con campos opcionales no nulos |
| `DatosPresupuesto.obra()` y `Entorno` crean una segunda empresa activa y la obra `AP-058-25`; con dos activas el alta responde `500` por `A9` | Notas de ejecución de `design.md`; TC-13, TC-31 | Toda prueba que haga un alta y siembre obras por otro camino |
| El menú del armazón se agrupa por grupo, no por el orden de `SECCIONES`: una sección al final de la tabla sale primera en el menú de un rol que no ve nada de su grupo | `Armazon.test.tsx`, TC-F05 | Cualquier sección nueva |
| Un `23505` de un índice único trae `diag.constraint_name`, lo que permite distinguir el duplicado del código de cualquier otra violación | `test_tkt011_estructura.py`, TC-11 | Cualquier unicidad que deba traducirse a `409` |
| Un test de concurrencia determinista pausa al primer hilo dentro de `insertar_obra` y espera con `pg_blocking_pids` a que el segundo quede bloqueado; un `Barrier` solo puede pasar sin solaparse | TC-12 | Cualquier carrera arbitrada por un índice |
| `npm run e2e` reutiliza el servidor del puerto 5173 si ya hay uno; si es de otro proyecto, las pruebas fallan por razones ajenas al cambio | Primera corrida de B5 | Antes de cualquier ejecución de `npm run e2e` |

## Observaciones para `_evolucion.md`

Fricción del **proceso**, no del producto.

| Tema | Observación | Severidad |
|---|---|---|
| `comando` | La comprobación de Docker de `/sdd-ejecutar` (`docker info` con `head -3`) solo mostró la parte del cliente y dio por bueno un demonio caído; hay que comprobar `Server Version` o que el comando no falle, y repetirlo antes de cada fila con base | Media |
| `herramienta` | `npm run e2e` reutiliza (`reuseExistingServer`) un Vite de otro repositorio que ocupaba el puerto 5173 y sirvió otra aplicación; el rojo salió por una razón ajena y la corrida en verde exigió detener ese proceso | Media |
| `agente` | `auditor-docs` afirmó en el primer ciclo que ADR-031 no existía (la numeración es ordinal por posición en el índice y el id sí existe); en el segundo, que existía pero no cubría el caso. Costó dos ciclos y el texto «literal esperado» no coincidió con lo que acabó escrito | Media |
| `plantilla` | La spec (`CA-R3`: «sin modificarlas») y el diseño («las 19 de TKT-008c») contaban una cifra que no se comprobó con un comando (eran 21) y no preveían que una etiqueta compartida obliga a actualizar una prueba heredada; apareció como choque en la fila B1 | Media |
| `comando` | `/sdd-ejecutar` ejecuta una entrega por pasada, pero la persona dueña pidió «entregas a y b» en una sola sesión; funcionó, pero el comando no dice cómo encadenarlas ni cuándo corre `/sdd-revisar` entre ellas | Baja |
| `agente` | Un tester marcó como `(asumido)` la forma de `opciones`, que el diseño ya fijaba: no cruzó el diseño con el supuesto | Baja |
| `guardrail` | Existía una rama local de otro slug, sin commits, que bloqueó la apertura de la rama del ticket y exigió una pregunta; `/sdd-definir` debería fijar el slug de la rama en el hub y detectar ramas previas | Baja |
| `herramienta` | Los agentes en Windows escribieron archivos de evidencia con CRLF y en cp1252 (`.txt` con acentos no UTF-8) y `auditor-docs` abrió Menores; es el mismo patrón de CRLF de TKT-017 | Baja |
| `herramienta` | Un límite de uso de la cuenta cortó un agente a mitad de la fila A4; `SendMessage` lo reanudó sin pérdida, pero el agente había escrito el archivo entero desde cero porque no había guardado nada | Baja |

## Deuda que queda abierta

| Qué | Por qué se dejó | Ticket sugerido |
|---|---|---|
| `actualizar_obra`, `eliminar_obra`, `suspender_obra`, `reactivar_obra` y `cerrar_obra`, y el escenario 20 de HDU-001 | Partición de TKT-012 por el plazo; sus huecos de reglas (qué cuenta como «movimientos» en `OBRA_CON_HISTORIAL`, la acción de bitácora del borrado) no están resueltos | TKT-012b |
| Selector de obra del armazón (wireframe §2) y ficha de solo lectura de la obra (`/obras/{id}`, destino natural de «Ver la obra») | Recorte de `D-7` por el plazo | Ticket por abrir (selector y ficha de obra); asignación de id de la persona dueña |
| `listar_tipos_partida` y `listar_insumos` | Se construyen con su primer consumidor; en `docs/07` siguen con `TKT-012` (hallazgo N002 de `auditor-docs`) | TKT-018b (previsualización de la importación) o el ticket de la captura de requisición (HDU-002) |
| Qué ve la persona si el alta devuelve un bloqueo de negocio o de concurrencia: el formulario se cierra y se pierde lo capturado | El borrador no declara esos `409` para `crear_obra`; el diseño no define el caso | Decisión pendiente de la persona dueña · ticket por abrir tras decidir |
| Botón `+` visible en todos los estados de la lista, y textos de la pantalla (estado vacío, rótulos, nombres de estado) redactados por el desarrollador | El diseño no los fija | Decisión pendiente de la persona dueña · ticket por abrir tras decidir |
| El cliente rechaza por formato un umbral de `-5` o `1000`, y el servidor habría respondido `FUERA_DE_RANGO` | TC-F01 lo aprobó así; el cliente decide una parte de `PA-18` | Decisión pendiente de la persona dueña · ticket por abrir tras decidir |
| Duplicación de la lectura de `sqlstate` y `constraint_name` entre `aplicacion/obras.py` y `traduccion_motor.py` (F002 de `auditor-codigo`) | Quitarla exige tocar un archivo de TKT-017; aceptada como deuda | Ticket de limpieza por abrir; id pendiente de la persona dueña |
| `Any` sin justificar en auxiliares de pruebas (F007 de `auditor-codigo`) | Ningún desarrollador edita tests; aceptada como deuda | Ticket de limpieza por abrir; id pendiente de la persona dueña |
| `test_tkt012a_api_alta_sin_permiso` sin escenario HDU en el nombre (F011) | `CA-6` no tiene escenario HDU y HDU-001 no tiene escenario de permiso | Decisión pendiente de la persona dueña · ticket por abrir tras decidir |
| `_sin_nul` dice «El motivo no admite el carácter NUL» y se reutiliza en `codigo`, `nombre` y `domicilio` (F002 de `auditor-seguridad`) | Mensaje compartido con TKT-017 | Ticket de limpieza por abrir; id pendiente de la persona dueña |
| El permiso por obra no existe en el MVP: `listar_obras` y `obtener_obra` no filtran por asignación (F001 de `auditor-seguridad`) | `docs/07`: «en el MVP no hay permiso por obra» | El ticket que introduzca la asignación usuario-obra (aún sin id); debe filtrar el listado, no solo validar el parámetro |
| `tkt-029a/design.md` reserva «ADR-041» y el ADR de este ticket ocupa ese ordinal | Aviso de `auditor-docs` (N008) | TKT-029a: usar el siguiente número libre |
| Si falla un refetch de la lista (p. ej. tras un alta), el aviso de error sustituye la tabla aunque ya hubiera datos cargados (revisión con `code-review`) | Hallazgo de la revisión previa al PR; no cambia lo aprobado en el diseño y no tiene prueba | Ticket de limpieza por abrir; id pendiente de la persona dueña |
| La lista pide una sola página de 200 obras y no pagina: de la 201 en adelante son inalcanzables (`D-4`, `code-review`) | Decisión aprobada para el MVP | El ticket del selector de obra, que consume `listar_obras` |
| El foco inicial de `FormularioCatalogo` solo se asigna si el primer campo es de texto | Hoy ningún formulario empieza por casilla o desplegable | El primer ticket de formulario que empiece por casilla o desplegable (aún sin id) |

## Pull request

**Título:** `TKT-012a · Alta y consulta de obras`
**Origen:** `agent`. El código lo escribieron agentes; la persona dueña decidió el alcance y las decisiones de la sesión, pero no revisó el código línea por línea.
**Cuerpo:** qué (las tres rutas de obra y su pantalla), por qué (primer paso de la línea base de HDU-001: sin obra no hay presupuesto), criterios cubiertos (`CA-1` a `CA-13` y `CA-R1` a `CA-R3`), cómo verificarlo (`uv run pytest`, `npm test`, `npm run e2e`) y una línea por entrega.

**Fusión con omisión:** el registro no va en este archivo. Va en un comentario del PR que el orquestador deja justo después de `gh pr merge --admin`, con la aprobación explícita de la persona dueña en la sesión.
