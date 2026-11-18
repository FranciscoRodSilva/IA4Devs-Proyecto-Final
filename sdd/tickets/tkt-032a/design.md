# Design · TKT-032a · Pantalla del catálogo de proveedores

> [← index](_index.md) | [← spec](spec.md) | Siguiente: impl (se enlaza en `/sdd-ejecutar`)

## Estrategia

El ticket es **solo frontend**: sustituye el marcador de la sección «Proveedores» por una pantalla que consume las seis rutas de `/api/v1/proveedores` ya fusionadas, sin ninguna ruta ni campo nuevo del contrato. Sigue el patrón de la pantalla de obras de TKT-012a (consultas, esquema de formulario y pantalla en tres archivos) y reutiliza lo de TKT-008c: `FormularioCatalogo` para el alta y la edición, `CapturaMotivo` para desactivar y dar de baja, y `PantallaBloqueo` para el `409` de la baja. Las dos operaciones de estado se ofrecen **como botones de cada fila**, no dentro del formulario de edición, para que «Desactivar» y «Dar de baja» se distingan a simple vista (objeción 3 de la spec) y para que la acción «Desactivar» del bloqueo se **tome de `acciones[]` del servidor**, nunca se cablee. La primera fila del orden es el boceto y la reconciliación de la baja en `docs/08-wireframes.md` (decisión D-1 de la spec), para que la persona dueña lo vea antes de que exista código.

El orden suma unas 540 líneas de producción, así que se ejecuta en **dos entregas** sobre una sola rama y un solo PR: **a** (boceto, extensiones compartidas, consultas, lista y alta, ~340 líneas) y **b** (edición, desactivar, baja y bloqueos, contrato y extremo a extremo, ~200 líneas más la prueba). Ver «Partición en entregas».

## Hallazgos para `/sdd-escalar`

Dos cosas que el diseño encontró y **no resuelve por su cuenta**, porque tocan el backend o el contrato (non-goal de la spec). Ninguna impide aprobar el diseño: cada una tiene una salida que sí cabe en el ticket.

| # | Hallazgo | Qué ve el diseño | Salida que cabe en el ticket | Salida que no cabe |
|---|---|---|---|---|
| H-1 | **No existe «la acción de verlo» del proveedor duplicado.** `CA-3` pide que el conflicto `RFC_DUPLICADO` muestre al proveedor existente «con la acción de verlo». El backend responde `acciones=()` (`_rechazo_rfc_duplicado`, `backend/cimenta/proveedores/aplicacion/proveedores.py`), el borrador OpenAPI solo cita el código y ninguna clave `VER_PROVEEDOR` existe en el contrato. Además `ConflictoEnLinea` solo dibuja botones que vienen en `acciones[]`, y el cliente no cablea ninguno (`docs/08-wireframes.md` §6) | El conflicto pinta el mensaje y la cifra «Proveedor existente: CoPanel · XAXX010101000», sin botón | **Recomendada.** Reescribir `CA-3` a «muestra el proveedor existente» y dejar la acción de verlo para un ticket que añada `VER_PROVEEDOR` al backend. Quien necesite abrirlo lo encuentra con la búsqueda por RFC y el filtro «Todos» | Añadir `VER_PROVEEDOR` (`GET /api/v1/proveedores/{id}`) a `acciones[]` de `RFC_DUPLICADO`: cambia `proveedores.py`, `openapi.yaml` y las pruebas de TKT-029a. Es un ticket de backend, no de esta pantalla |
| H-2 | **El E2E de `CA-8` exige un archivo nuevo en `backend/herramientas/`.** La decisión D-3 manda sembrar una orden `PARCIAL` con `sembrar_orden_compra`, pero esa función solo es una ayuda de pruebas de pytest: ningún script la llama y su docstring dice que «ningún código de producción la importa». Para que Playwright la use hace falta un sembrador local, como `semilla_linea_base_local.py` | Un archivo nuevo, `backend/herramientas/semilla_orden_proveedor_local.py` (~60 líneas), más una línea del docstring de `soporte_tkt029b_ordenes.py` | Aprobar que ese archivo cuenta como **apoyo de pruebas** y no como cambio al backend de producto: no toca `cimenta/`, ni el contrato, ni el esquema, y niega cualquier base que no sea local (`exigir_base_local`). La Definition of Done de la spec («ningún cambio al backend ni a `openapi.yaml`») se lee entonces «ningún cambio a `cimenta/`, a las migraciones ni a `openapi.yaml`» | Sin él, `CA-8` solo se probaría con respuestas simuladas (MSW) y el E2E dejaría de cubrir el `409` real, contra lo decidido en D-3 |

## Decisiones para el gate

Cinco decisiones que aparecieron al diseñar (D-6 a D-10), además de D-2, D-4, D-5 y S-1 de la spec, que siguen vigentes como están (D-1 y D-3 ya están resueltas). **La persona dueña aprobó el 2026-11-17 el boceto de F1 y D-6 a D-10 con la recomendación de cada fila**; donde dice «Recomendación provisional» léase «aprobada». Las filas de la ejecución citan la decisión. Siguen abiertos H-1 y H-2.

| # | Pregunta | Recomendación provisional | Qué cambia con otra opción |
|---|---|---|---|
| D-6 | **Texto del `403`.** `CA-9` dice que la pantalla pinta «No tienes permiso»; el servidor manda «Tu rol no permite esta operación.» (`ROL_INSUFICIENTE`) | Mostrar el `mensaje` que manda el servidor, como se aprobó en D-6 de TKT-012a, y corregir el texto de `CA-9` y del boceto de `docs/08` §6 en la misma aprobación. Sin cifras en ningún caso | «Texto literal»: `FormularioCatalogo` ganaría una rama `PERMISO` con texto fijo (toca el componente compartido y rompería su coherencia con obras); `CapturaMotivo` no lo admite sin cambio. Más código y deriva respecto de TKT-012a |
| D-7 | **Qué acciones ofrece cada estado.** La spec fija «Desactivar» solo en `ACTIVO` y «Dar de baja» en `ACTIVO` y `DESACTIVADO`, y dice que sobre `BAJA` no se ofrece nada. Calla sobre «Editar». El servidor no comprueba el estado al editar (`actualizar_proveedor`, D-3 de TKT-029a) | **Editar** en `ACTIVO` y `DESACTIVADO`, no en `BAJA`: corregir un dato de un proveedor desactivado es legítimo y `CA-7` prohíbe cualquier acción sobre uno dado de baja | «Editar solo en `ACTIVO`»: una condición menos en la fila. «Editar también en `BAJA`»: contradice `CA-7` y la baja deja de ser terminal en la práctica (`PA-24`) |
| D-8 | **Dónde viven «Desactivar» y «Dar de baja».** `FormularioCatalogo` ya trae una ranura `baja` que pone un solo botón dentro del formulario de edición | **Botones de cada fila** (`Editar`, `Desactivar`, `Dar de baja`), sin usar la ranura `baja`. Dos operaciones con efectos distintos no caben en una ranura pensada para una; en la fila se ve a la vez qué se ofrece a cada estado, y la acción del bloqueo reutiliza el mismo flujo de desactivar | «Dentro del formulario»: la baja pasa a ser un botón del diálogo de edición y «Desactivar» necesitaría otra ranura nueva en el componente compartido (tocarlo rompe `CA-R2` si se hace mal) |
| D-9 | **«Junto al campo» del conflicto `RFC_DUPLICADO`.** `CA-3` pide el error «junto al campo RFC». El componente compartido pinta todo `409` de tipo `CONFLICTO` **debajo de los campos y encima de los botones**, que es lo que aprobó el boceto de obras | Aceptar la ubicación del componente (debajo de los campos, dentro del formulario, que sigue abierto y conserva lo capturado) y leer `CA-3` como «dentro del formulario». El campo RFC no se marca `aria-invalid`: no es un error de forma sino un dato que ya existe | «Pegado al campo»: `FormularioCatalogo` necesitaría una prop nueva para colocar el conflicto bajo un campo concreto; solo lo pide este ticket |

**D-10 · Cambio declarado a una prueba de TKT-008c** (la revisión de impacto lo encontró; sin tu aprobación `CA-R2` se incumpliría).

| # | Pregunta | Recomendación provisional | Qué cambia con otra opción |
|---|---|---|---|
| D-10 | La etiqueta «Desactivar el proveedor» rompe cuatro líneas de `FormularioCatalogo.test.tsx` (443, 445, 447, 456), que buscan el botón por la clave cruda `DESACTIVAR_PROVEEDOR`. `CA-R2` pide esas pruebas «sin cambios» | Aprobar el cambio de esas cuatro líneas (el mismo tipo de ajuste que la persona dueña aprobó el 2026-11-10 en TKT-012a con `VER_OBRA`), y leer `CA-R2` como «ningún comportamiento del formulario cambia» | «Sin etiqueta»: el botón del bloqueo diría `DESACTIVAR_PROVEEDOR` en pantalla, contra el boceto y TC-F03; las pruebas de TKT-008c no se tocan |

## Escalera de decisión

| Objeto | Peldaño donde paró | Por qué |
|---|---|---|
| Boceto «2c · Pantalla Proveedores» y reconciliación de la baja en `docs/08-wireframes.md` | 4 · cambio mínimo | Se añade una subsección a la pantalla 2 y se corrige una viñeta de la pantalla 8; ninguna otra se mueve |
| Alta y edición del proveedor | 3 · reuso | `FormularioCatalogo` ya trae diálogo, foco en el primer campo, validación con Zod, error `422` por campo, conflicto en línea y conservación de lo capturado (TKT-008c, probado por 24 tests) |
| RFC de solo lectura en la edición (`CA-5`) | 4 · cambio mínimo | `CampoTextoCatalogo` gana la propiedad opcional `soloLectura` que pinta el `<input>` con `readOnly`. El camino del texto, el correo y la fecha no cambia. Quitar el campo de la edición contradice `CA-5` («el RFC aparece de solo lectura»); pintarlo fuera del formulario obliga a duplicar el diálogo |
| Desactivar y dar de baja con motivo | 3 · reuso | `CapturaMotivo` ya valida el motivo obligatorio, conserva lo escrito ante un `422` y entrega todo otro rechazo a la pantalla por `alRechazo` |
| Bloqueo de la baja, estado ya no válido y espera de bloqueo | 3 · reuso | `PantallaBloqueo` pinta `CONFLICTO` y `CONCURRENCIA` con su cabecera, sus cifras, sus acciones y «Cerrar». La pantalla no recalcula nada y no filtra acciones |
| Tabla `ordenes` en `TABLAS_DETALLE`, rótulo `proveedor_existente`, clave oculta `proveedor_existente_id` y etiqueta `DESACTIVAR_PROVEEDOR` en `etiquetas.ts` | 4 · cambio mínimo | Hoy `DetalleCifras` pinta `ordenes` como JSON crudo y el id del proveedor como clave desconocida, y el botón se rotularía con la clave cruda. Son cuatro líneas de datos; el componente no cambia. Mismo patrón que `obra_existente` de TKT-012a |
| Enteros 1 a 7 de día de corte y de pago | 3 · reuso | `enteroNoNegativo` de `compartido/dinero/dinero.ts` ya es la única puerta permitida de cadena a entero (la regla de ESLint prohíbe `Number`, `parseInt` y `parseFloat` fuera de ese módulo, `PA-T11`). No se escribe un convertidor nuevo |
| Tope de consignación | 3 · reuso | `aDecimal` y `Decimal` de `dinero.ts` comparan; `formatearImporte` presenta. El valor viaja siempre como cadena (`CA-R4`) |
| Qué cambió en una edición (cuerpo del `PATCH`) | 5 · objeto nuevo, local | `ProveedorCambios` exige al menos una propiedad (`minProperties: 1`) y la bitácora asienta lo enviado; mandar solo lo cambiado evita un `ACTUALIZAR` sin cambio. Una función pura de ~20 líneas en `proveedores.formulario.ts` |
| `EsqueletoLista` y `AvisoErrorLista` | 5 · copia local | Hoy son privados de `PantallaObras.tsx`. Extraerlos tocaría esa pantalla, que TKT-012b está modificando en paralelo (conflicto seguro). Se copian ~40 líneas en un archivo propio y se anota en «Riesgos» el ticket de refactor para cuando 012b esté fusionado |
| Filtro por estado y búsqueda | 2 · nativo | `<select>` y `<input type="search">` del navegador, con `Label`, como el desplegable de `FormularioCatalogo`. shadcn no tiene instalados `select` ni `checkbox` |
| Paginación | 5 · objeto nuevo | Ninguna pantalla pagina todavía (obras pide una sola página de 200). Dos botones «Anterior» y «Siguiente» y el texto «Página N de M»; el `total` lo da `paginacion` |
| `proveedores.consultas.ts`, `proveedores.formulario.ts` y `PantallaProveedores.tsx` | 5 · objeto nuevo | Son la pantalla; no hay otra con datos de proveedor |
| Sembrador local de una orden `PARCIAL` | 5 · objeto nuevo | Ver H-2. Reutiliza `sembrar_orden_compra` y `exigir_base_local`; no escribe lógica de órdenes propia |

Ningún objeto paró en el peldaño 4 sobre un invariante registrado: la escalera no se rompe. `CLAUDE.md` regla 8 (el cliente nunca decide) se cumple: ninguna fila calcula si un proveedor «puede» darse de baja; la pantalla ofrece el botón por el **estado que ya devolvió el servidor** y el `409` lo decide el servidor.

## Capas afectadas

### Frontend

Rutas del contrato que la pantalla usa, todas de `servidor.ts`: `GET /api/v1/proveedores` (`listar_proveedores`), `POST /api/v1/proveedores` (`crear_proveedor`), `PATCH /api/v1/proveedores/{proveedor_id}` (`actualizar_proveedor`), `POST …/desactivacion` (`desactivar_proveedor`) y `POST …/baja` (`dar_baja_proveedor`). `obtener_proveedor` no se usa: la fila ya trae todos los campos.

| Componente o vista | Datos | Estados |
|---|---|---|
| `frontend/src/modulos/proveedores/catalogo/proveedores.consultas.ts` (nuevo) | `claves = { proveedores: ["proveedores"] as const }`. `proveedoresOptions(api, { estados, q, pagina })` con `queryOptions` y `queryKey: [...claves.proveedores, "lista", { estados, q, pagina, tamano_pagina: 50 }]`, que llama a `api.GET("/api/v1/proveedores", { params: { query } })`; `estado` se envía **siempre** (por omisión `["ACTIVO"]`) y `q` solo si no está vacía (D-5). `crearProveedor(api, cuerpo)`, `actualizarProveedor(api, id, cambios)`, `desactivarProveedor(api, id, motivo)` y `darDeBajaProveedor(api, id, motivo)`: cada una `pedir(() => api.…)` sin lanzar. Tras cada mutación exitosa, `queryClient.invalidateQueries({ queryKey: claves.proveedores })` | — |
| `frontend/src/modulos/proveedores/catalogo/proveedores.formulario.ts` (nuevo) | Dos esquemas Zod que **no** espejan el modelo (validan el formulario): (`*.formulario.ts` no puede importar `decimal.js` directamente, regla de ESLint: `Decimal` y `aDecimal` se toman de `@/compartido/dinero/dinero`) `esquemaAlta` (`nombre` recortado, 1 a 200 caracteres y sin `NUL`; `rfc` recortado y en mayúsculas con el patrón `^[A-ZÑ&]{3,4}[0-9]{6}[A-Z0-9]{3}$` como cortesía; `tope_consignacion` vacío → `null` o `^[0-9]{1,14}(\.[0-9]{1,4})?$` que se envía **tal cual como cadena**; `dia_corte` y `dia_pago` como texto `"1"` a `"7"` que se convierte con `enteroNoNegativo`) y `esquemaEdicion` (lo mismo con `rfc` solo de lectura). Constantes `DIAS` (`1` lunes … `7` domingo, en minúsculas como la spec), `VALORES_INICIALES_ALTA` (`dia_corte: "4"`, `dia_pago: "6"`, `tope_consignacion: ""`), `camposAlta`, `camposEdicion` (el RFC con `soloLectura: true`, segundo en el orden: el primero sigue siendo de texto y recibe el foco), `valoresInicialesDe(proveedor)` y `cambiosDe(proveedor, valores): ProveedorCambios \| null` que devuelve solo lo distinto (el tope se compara con `Decimal.eq`, nunca como número) o `null` si nada cambió | — |
| `frontend/src/modulos/proveedores/catalogo/estados-lista.tsx` (nuevo) | `EsqueletoLista` (`role="status"` y `aria-busy`, etiqueta «Cargando los proveedores»), `AvisoErrorLista` (mensaje, `Referencia: correlacion_id` y botón «Reintentar») y `SinProveedores` | los tres estados no felices de la lista |
| `frontend/src/modulos/proveedores/catalogo/PantallaProveedores.tsx` (nuevo) | `useQuery(proveedoresOptions(...))`; `useSesion()` para decidir si se pintan las acciones: **solo `COMPRAS`** (los otros cinco roles consultan, D-2). Cabecera «Proveedores» con el botón `+` (`aria-label` «Dar de alta un proveedor»); barra con el filtro «Estado» (`Activos` por omisión, `Desactivados`, `Dados de baja`, `Todos`, que envía los tres estados), la búsqueda por nombre o RFC (aplica al pulsar «Buscar» o Enter, sin temporizador) y, bajo la tabla, «Anterior», «Página N de M» y «Siguiente». Si la página pedida llega vacía pero `paginacion.total` es mayor que cero, la pantalla pide la última página con datos. Tabla con Nombre, RFC, Estado, Corte, Pago y Acciones. El estado se rotula en español (`Activo`, `Desactivado`, `Baja`) y `Desactivado` y `Baja` van en gris, con texto, no solo color (el *Should*). Por fila: **Editar** (`ACTIVO` y `DESACTIVADO`, D-7), **Desactivar** (solo `ACTIVO`) y **Dar de baja** (`ACTIVO` y `DESACTIVADO`); `BAJA` no lleva ninguna. Cada botón lleva el nombre del proveedor en su `aria-label` («Editar CoPanel»). Dos `FormularioCatalogo` (alta «Alta de proveedor» y edición «Editar proveedor»), una `CapturaMotivo` compartida por desactivar y baja, y la `PantallaBloqueo` en línea sobre la tabla cuando una operación de estado responde `409`. `alAccion` entrega `DESACTIVAR_PROVEEDOR` al flujo de desactivar **del mismo proveedor** y la pantalla no ofrece ningún botón que el servidor no haya enviado | **cargando** (esqueleto), **vacío** («No hay proveedores con este filtro» y, con el filtro por omisión y `COMPRAS`, la invitación al `+`), **con proveedores**, **error** (aviso con `correlacion_id` y «Reintentar») y **bloqueado** (`PantallaBloqueo` con el `409` de la baja o del estado). El `403` y el `404` de una operación se pintan en un aviso sobre la tabla |
| `frontend/src/modulos/proveedores/rutas.tsx` | `{ path: "compras/proveedores", element: <GuardaSeccion clave="PROVEEDORES"><PantallaProveedores /></GuardaSeccion> }` en lugar de `rutaMarcador("PROVEEDORES")`; la ruta y la guarda son las mismas (`CA-R1`) | — |
| `frontend/src/compartido/componentes/bloqueo/etiquetas.ts` | `TABLAS_DETALLE` gana `{ clave: "ordenes", titulo: "Órdenes pendientes", columnas: [Folio · folio · texto, Estado · estado · texto] }`; `CLAVES_DETALLE` gana `{ clave: "proveedor_existente", etiqueta: "Proveedor existente", formato: "texto" }`; `CLAVES_OCULTAS` gana `"proveedor_existente_id"`; `ETIQUETAS_ACCION` gana `DESACTIVAR_PROVEEDOR: "Desactivar el proveedor"`; `CLAVES_DETALLE` gana además `{ clave: "estado_actual", etiqueta: "Estado actual", formato: "texto" }` (el `detalle` de `ESTADO_NO_PERMITE_OPERACION`, que hoy saldría como clave cruda) | — |
| `frontend/src/compartido/formularios/FormularioCatalogo.tsx` | `CampoTextoCatalogo` gana `soloLectura?: boolean`; `CampoFormulario` pasa `readOnly` y `aria-readonly` al `Input`. Nada más cambia | — |

**Cómo se pinta cada rechazo** (el servidor decide, la pantalla pinta):

| Respuesta | Dónde | Qué ocurre |
|---|---|---|
| `422` del alta o la edición | `FormularioCatalogo` (ya existe) | Mensaje junto al campo por `errores[].campo`, formulario abierto, lo capturado se conserva |
| `409` `RFC_DUPLICADO` | `FormularioCatalogo` → `ConflictoEnLinea` (ya existe) | Debajo de los campos (D-9), con «Proveedor existente: nombre · RFC» (clave nueva de `etiquetas.ts`); sin botón (H-1); sin fila nueva |
| `404` al editar | `alGuardar` de la pantalla envuelve la respuesta | Devuelve el mismo error al formulario (aviso en la cabecera) e **invalida la lista** para recargarla (`CA-5`) |
| `422` del motivo | `CapturaMotivo` (ya existe) | Mensaje junto al campo; el botón «Confirmar baja» no envía un motivo vacío |
| `409` `PROVEEDOR_CON_ORDENES_ABIERTAS` | `alRechazo` de `CapturaMotivo` → `PantallaBloqueo` sobre la tabla | Cierra el diálogo, pinta las órdenes (folio y estado), y sus botones son los de `acciones[]`: con el proveedor `ACTIVO` el servidor manda `DESACTIVAR_PROVEEDOR` y el botón abre la captura de motivo de desactivar para **ese** proveedor; con `DESACTIVADO` manda `acciones: []` y solo queda «Cerrar» (`CA-8`) |
| `409` `ESTADO_NO_PERMITE_OPERACION` | igual | `PantallaBloqueo` con el mensaje del servidor e invalidación de la lista: la fila vuelve con su estado actual (`CA-10`) |
| `409` `CONCURRENCIA` | igual | `PantallaBloqueo` con «Reintentar» (espera `Retry-After`); `alReintentar` vuelve a abrir la captura de motivo de la misma operación |
| `403` | aviso sobre la tabla (o la cabecera del formulario) | El `mensaje` del servidor, sin cifras (D-6). El cliente de la API ya vuelve a preguntar quién es el usuario |
| `401` | cliente de la API (ya existe) | Redirige al inicio de sesión (`CA-9`) |
| Red o `500` | aviso con `Referencia` si la hay | La pantalla no cae |

## Partición en entregas

Una sola rama `tkt-032a-pantalla-proveedores`, un solo PR que abre `/sdd-completar` al aprobarse la última entrega.

| Entrega | Filas | Criterios que cierra | Líneas de producción estimadas |
|---|---|---|---|
| **a · boceto, lista y alta** | F1 a F6 | `CA-1`, `CA-2`, `CA-3`, `CA-4`, `CA-9`, `CA-R1`, `CA-R4` (parte de alta) | ~340 (etiquetas y formulario compartido 25, consultas 55, esquema 90, estados de lista 40, pantalla de lista y alta 130; el boceto son ~110 líneas de documentación aparte) |
| **b · edición, estado y extremo a extremo** | F7 a F10 | `CA-5` a `CA-8`, `CA-10`, `CA-11`, `CA-R2`, `CA-R3`, resto de `CA-R4` | ~200 (edición 30, desactivar, baja y bloqueos 100, sembrador local 60, ayuda de siembra de Playwright 25; la prueba de Playwright son ~90 líneas aparte) |

La entrega a cierra el catálogo en modo lectura más el alta, que ya le sirve a Compras; la b añade lo que cambia el estado de un proveedor. Cada fila declara abajo cuántas líneas tiene: ninguna pasa de 130.

## Orden de implementación

Se ejecuta fila por fila con el ciclo TDD de [metodología §16](../../metodologia.md#16--el-ciclo-tdd): rojo, verde, refactor. La verificación de cada paso corre **antes** de pasar al siguiente. Comandos de `frontend/` salvo que se diga otra cosa; `npm run e2e` necesita Docker en marcha, la base migrada y `npx playwright install chromium`.

| # | Paso | Tests que pone en verde | Agente | Modelo | Verificación | Estado |
|---|---|---|---|---|---|---|
| **F1** | **Boceto del catálogo y reconciliación de la baja en `docs/08-wireframes.md`**: subsección «2c · Pantalla Proveedores» tras la 2b y la viñeta *Proveedor* de la pantalla 8, con el texto exacto de «Boceto de la primera fila». Es **la fila que revisa la persona dueña antes de escribir código**: sus observaciones se incorporan aquí y a este diseño antes de F2 | — (documentación; no hay rojo que escribir) | `desarrollador-react` | `haiku` · el texto va escrito en este diseño | `python tools/verificar_docs.py` desde la raíz (enlaces, anclas, conteos, codificación) y `markdownlint-cli2` sobre `docs/08-wireframes.md`; la persona dueña da el visto bueno al boceto | ✓ Hecho (entrega a) |
| F2 | `etiquetas.ts`: tabla `ordenes`, `proveedor_existente`, clave oculta y etiqueta `DESACTIVAR_PROVEEDOR` | TC-F01 a TC-F03 (en `ConflictoEnLinea.test.tsx` y `PantallaBloqueo.test.tsx`, pruebas nuevas) | `desarrollador-react` | `haiku` | `npm test -- PantallaBloqueo ConflictoEnLinea FormularioCatalogo CapturaMotivo` con todas las existentes en verde; el único cambio permitido a una prueba existente son las cuatro líneas de D-10 (`FormularioCatalogo.test.tsx:443`, `:445`, `:447` y `:456`), citando D-10 en `impl.md`; `npm run lint`; `npm run typecheck` | ✓ Hecho (entrega a) |
| F3 | `FormularioCatalogo` con `soloLectura` | TC-F04 (nueva en `FormularioCatalogo.test.tsx`) | `desarrollador-react` | `haiku` | `npm test -- FormularioCatalogo` con las 24 de TKT-008c sin modificar y la nueva en verde; **si TKT-012b ya introdujo `soloLectura` (su fila B1), esta fila se elimina** y se rebasa | ⚠ Ajustado · eliminada: TKT-012b (PR #80, ya fusionado) introdujo `soloLectura` en `FormularioCatalogo.tsx`; ver «Ajustes de la ejecución» |
| F4 | `proveedores.consultas.ts` y `proveedores.formulario.ts` | TC-F05 a TC-F08 (`proveedores.formulario.test.ts` y `proveedores.consultas.test.ts`) | `desarrollador-react` | `haiku` | `npm test -- proveedores`; `npm run lint` (la regla de `Number` no se dispara); `npm run typecheck`; `npm run tipos:verificar` | ✓ Hecho (entrega a) |
| F5 | `estados-lista.tsx`, la lista de `PantallaProveedores.tsx` (filtro, búsqueda, paginación, acciones por rol y por estado, y el botón `+` pintado solo para Compras, que F6 conecta al formulario) y `rutas.tsx` con la pantalla en lugar del marcador | TC-F09 a TC-F16 (`PantallaProveedores.test.tsx`, con MSW), TC-F17 (`CA-R1`) | `desarrollador-react` | `sonnet` · disparador «los permisos de un rol» (§14.2): decide qué acciones ve cada rol y cada estado | `npm test -- PantallaProveedores secciones Armazon`; mutantes `M-1`, `M-2`, `M-3` y `M-5` de esta fila; `npm run lint`; `npm run typecheck` | ✓ Hecho (entrega a) |
| F6 | El alta en `PantallaProveedores.tsx`: botón `+`, formulario, `422` por campo y conflicto `RFC_DUPLICADO` | TC-F18 a TC-F22 | `desarrollador-react` | `haiku` | `npm test -- PantallaProveedores`; mutante `M-4` (tope como número) | ✓ Hecho (entrega a) |
| F7 | La edición: formulario con RFC de solo lectura, `PATCH` solo con lo cambiado, `404` que recarga | TC-F23 a TC-F26 | `desarrollador-react` | `haiku` | `npm test -- PantallaProveedores` | ✓ Hecho (entrega b) |
| F8 | Desactivar y dar de baja: captura de motivo, `PantallaBloqueo` con las órdenes y la acción tomada del contrato, estado ya no válido, espera de bloqueo | TC-F27 a TC-F36 | `desarrollador-react` | `sonnet` · disparador «los permisos de un rol» (§14.2): la acción del bloqueo debe salir de `acciones[]` y nunca cablearse, y la baja del rechazo con órdenes decide qué se ofrece | `npm test -- PantallaProveedores PantallaBloqueo FormularioCatalogo CapturaMotivo`; mutantes `M-6` y `M-7`; `npm run lint`; `npm run typecheck` | ✓ Hecho (entrega b) |
| F9 | Prueba de contrato `CA-R3` | TC-F37 (`proveedores.contrato.test.ts`) | `desarrollador-react` | `haiku` | `npm test -- proveedores.contrato`; `npm run tipos:verificar` en verde | ✓ Hecho (entrega b) |
| F10 | `backend/herramientas/semilla_orden_proveedor_local.py` (H-2), la ayuda `e2e/sembrar-orden.ts` y `e2e/proveedores.spec.ts`. `preparacion-global.ts` **no cambia**: el spec siembra la orden justo después de dar de alta al proveedor, con la obra `CIMENTA_HUMO_LB_OBRA_ID` y el usuario `CIMENTA_HUMO_CORREO` que la preparación ya deja | TC-E1 y TC-E2 | `desarrollador-aplicacion` (el sembrador) y `desarrollador-react` (la ayuda y el spec) | `haiku` | Desde `backend/`: `uv run --env-file ../.env python -m herramientas.semilla_orden_proveedor_local` contra una base local con un proveedor sembrado, `uv run lint-imports`, `uv run ruff check .`, `uv run mypy .` y `uv run python -m herramientas.verificar_float`. Desde `frontend/`: `npm run e2e` (las tres de `humo.spec.ts`, `obras.spec.ts`, `linea-base.spec.ts` y las nuevas); `python tools/verificar_docs.py` | ✓ Hecho (entrega b) |

**Modelo:** `haiku` por omisión; `sonnet` solo en F5 y F8, por el disparador citado. Nunca `opus` en una fila de ejecución.

**Detalle del sembrador de F10** (`backend/herramientas/semilla_orden_proveedor_local.py`), calcado de `semilla_linea_base_local.py`:

- Entradas por variable de entorno: `CIMENTA_SEMILLA_OC_RFC` (el proveedor que acaba de dar de alta el spec), `CIMENTA_SEMILLA_OC_OBRA_ID` (la obra de humo) y `CIMENTA_SEMILLA_OC_CORREO` (el solicitante, el usuario de Compras de humo). Ninguna tiene valor por omisión.
- Resuelve con SQL: el `proveedor_id` por RFC (falla con un mensaje si no existe), el `tipo_partida_id` de la clave `MUROS` y el `insumo_id` del código `MO-001`, que ya existen por `semilla_linea_base_local`; el solicitante por correo.
- Folio único por corrida: `OC-E2E-<8 hex>`, porque `uq_orden_compra_folio` y `uq_requisicion_folio` romperían la segunda corrida sobre la base acumulativa, y la ayuda exige el prefijo `OC-`.
- Un solo renglón `("10.0000", "4.0000")`: con saldo y algo recibido la orden es `PARCIAL` (E-2, comprobada por lectura de `compras/dominio/orden_compra.py`).
- La conexión sale de `crear_motor_aplicacion()` y de su `raw_connection()`; **confirma explícitamente** con `commit()`, porque `sembrar_orden_compra` «no abre transacción ni confirma».
- Niega cualquier base que no sea local con `exigir_base_local()` y deja como última línea de la salida `ORDEN_ID=<uuid>`.
- El docstring de `soporte_tkt029b_ordenes.py` pasa a decir «ningún código de producción la importa; solo las pruebas y los sembradores locales de `herramientas/`».
- `docs/arranque-local.md` lleva una línea con el sembrador, junto a los de humo.

### Boceto de la primera fila

Es el texto que F1 pega en `docs/08-wireframes.md` (**este diseño no lo edita**). La subsección se coloca entre el final de la 2b y el `---` que abre la pantalla 3.

````markdown
### 2c · Pantalla Proveedores

| | |
|---|---|
| **Rol** | Compras da de alta, edita, desactiva y da de baja · los seis roles consultan |
| **Historias** | TKT-032a, sobre HDU-004 esc. 1, 2, 3, 12 y 13 |
| **Endpoints** | `GET /proveedores` · `POST /proveedores` · `PATCH /proveedores/{proveedor_id}` · `POST /proveedores/{proveedor_id}/desactivacion` · `POST /proveedores/{proveedor_id}/baja` |

```text
┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Proveedores                                                                                            [ + ] │
│ Estado [ Activos v ]    [ Buscar por nombre o RFC________________ ] [ Buscar ]                               │
├────────────────────┬─────────────────┬────────────┬──────────┬──────────┬─────────────────────────────────────┤
│ Nombre             │ RFC             │ Estado     │ Corte    │ Pago     │ Acciones                            │
├────────────────────┼─────────────────┼────────────┼──────────┼──────────┼─────────────────────────────────────┤
│ CoPanel            │ XAXX010101000   │ Activo     │ jueves   │ sábado   │ [Editar] [Desactivar] [Dar de baja] │
│ Aceros del Bajío   │ ABA040312KT7    │ Activo     │ jueves   │ sábado   │ [Editar] [Desactivar] [Dar de baja] │
├────────────────────┴─────────────────┴────────────┴──────────┴──────────┴─────────────────────────────────────┤
│ [ Anterior ]                                Página 1 de 1                                      [ Siguiente ] │
└──────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

  Con el filtro «Todos»: un proveedor desactivado ofrece Editar y Dar de baja; uno dado de baja, ninguna acción.
  │ Pinturas del Norte │ PNO990101AB2  │ Desactivado│ jueves   │ sábado   │ [Editar]               [Dar de baja] │
  │ Ferretera Vieja    │ FVI870605XY9  │ Baja       │ martes   │ sábado   │                                      │

  Formulario · Alta de proveedor (se abre con el botón +; el foco queda en el nombre)
  ┌──────────────────────────────────────────────────────────────────────────┐
  │ Nombre                       [ CoPanel________________________ ]         │
  │ RFC                          [ XAXX010101000__________________ ]         │
  │ Tope de consignación         [ 300000.00______________________ ]  opcional│
  │ Día de corte                 [ jueves v ]                                │
  │ Día de pago                  [ sábado v ]                                │
  │                                                                          │
  │                                         [ Cancelar ]   [ Guardar ]       │
  └──────────────────────────────────────────────────────────────────────────┘

  Formulario · Editar proveedor (el RFC no se cambia)
  ┌──────────────────────────────────────────────────────────────────────────┐
  │ Nombre                       [ CoPanel S.A. de C.V.___________ ]         │
  │ RFC                          [ XAXX010101000 ]  solo lectura             │
  │ Tope de consignación         [ 300000.0000____________________ ]         │
  │ Día de corte                 [ jueves v ]                                │
  │ Día de pago                  [ viernes v ]                               │
  │                                         [ Cancelar ]   [ Guardar ]       │
  └──────────────────────────────────────────────────────────────────────────┘

  Conflicto en línea · el RFC ya existe (409 CONFLICTO, RFC_DUPLICADO)
  ┌──────────────────────────────────────────────────────────────────────────┐
  │ RFC                          [ XAXX010101000__________________ ]         │
  │ ! Ya existe un proveedor con el RFC XAXX010101000.                       │
  │ Proveedor existente  CoPanel · XAXX010101000                             │
  └──────────────────────────────────────────────────────────────────────────┘

  Captura de motivo · Desactivar / Dar de baja
  ┌──────────────────────────────────────────────────────────────────────────┐
  │ Dar de baja a CoPanel                                                    │
  │ La baja es definitiva: el proveedor no recibe órdenes ni vuelve a        │
  │ activarse, y su historial se conserva.                                   │
  │ Motivo   [ __________________________________________________ ]         │
  │                                        [ Cancelar ]   [ Confirmar baja ] │
  └──────────────────────────────────────────────────────────────────────────┘

  Bloqueo · baja con órdenes pendientes (409 CONFLICTO, PROVEEDOR_CON_ORDENES_ABIERTAS), proveedor ACTIVO
  ┌──────────────────────────────────────────────────────────────────────────┐
  │ NO SE PUEDE COMPLETAR                                                    │
  │ PROVEEDOR_CON_ORDENES_ABIERTAS                                           │
  │ CoPanel tiene 2 órdenes pendientes de recibir; se puede desactivar para  │
  │ órdenes nuevas conservando las existentes.                               │
  │   Órdenes pendientes                                                     │
  │   Folio              Estado                                              │
  │   OC-AP05825-0017    PARCIAL                                             │
  │   OC-AP05825-0021    ABIERTA                                             │
  │ [ Desactivar el proveedor ]   [ Cerrar ]                                 │
  │                                       Referencia: c3d4e5f6-a7b8-4901     │
  └──────────────────────────────────────────────────────────────────────────┘
  Con el proveedor ya DESACTIVADO el servidor no manda la acción: queda solo [ Cerrar ].
```

**Datos.** La lista muestra nombre, RFC, estado, día de corte y día de pago, ordenada por nombre y paginada de 50 en 50. Por omisión solo trae los `ACTIVO`, igual que el servidor: para ver los `DESACTIVADO` o los `BAJA` se cambia el filtro *Estado*. El día se muestra por su nombre (`1` lunes … `7` domingo, ISO 8601) y se envía como entero; el alta propone jueves y sábado (`RN-17`). El tope de consignación se captura como texto, se envía como cadena decimal y no tiene ninguna regla en el MVP (`RN-15` es v1.1).

**Acciones.**

- *`+` · Dar de alta un proveedor* abre el formulario con el foco en el nombre. Solo lo ve Compras; los otros cinco roles consultan la lista sin él. Ocultarlo es cortesía: el control es el `403` del servidor.
- *Buscar* filtra por nombre o RFC (`q`) y vuelve a la página 1; el filtro *Estado* también.
- *Editar* (`ACTIVO` y `DESACTIVADO`) abre el formulario con el RFC de solo lectura; envía solo los campos que cambiaron.
- *Desactivar* (solo `ACTIVO`) pide el motivo. El proveedor pasa a `DESACTIVADO`: sale del selector de órdenes nuevas, conserva sus órdenes pendientes y su historial, y **no vuelve a activarse** (no existe esa operación; `PA-24`).
- *Dar de baja* (`ACTIVO` y `DESACTIVADO`) pide el motivo. El proveedor pasa a `BAJA`, que es definitiva y conserva el RFC *(asumido, PA-24)*. Si tiene órdenes `ABIERTA` o `PARCIAL`, el servidor la rechaza y la pantalla muestra el bloqueo.
- *Desactivar el proveedor* del bloqueo existe solo si el servidor la manda en `acciones[]` (proveedor `ACTIVO`) y abre el mismo motivo de desactivar.

**Estados.**

- **Cargando.** Esqueleto con la etiqueta accesible *Cargando los proveedores*.
- **Vacío.** *"No hay proveedores con este filtro."* Con el filtro por omisión, a Compras se le dice *"Da de alta el primer proveedor con el botón +."*
- **Con proveedores.** La tabla del boceto.
- **Error.** *"No se pudo cargar la lista de proveedores."* con *Reintentar* y la referencia del error.
- **Bloqueado.** Aplica a *Dar de baja*, *Desactivar* y *Reintentar*: la [pantalla de bloqueo](#6-pantalla-de-bloqueo) se pinta sobre la tabla con el `409` que mandó el servidor.

**Estados de rechazo.**

- **RFC duplicado (`409` `CONFLICTO`, `RFC_DUPLICADO`).** En línea, debajo de los campos, con el proveedor existente y sin ninguna fila nueva. El formulario conserva lo capturado. El contrato no ofrece una acción para verlo; se encuentra con la búsqueda por RFC y el filtro *Todos*.
- **Campo vacío o con forma incorrecta (`422`).** Junto al campo, antes de enviar (*"Escribe el nombre del proveedor."*) o con el mensaje del servidor.
- **Baja con órdenes pendientes (`409` `PROVEEDOR_CON_ORDENES_ABIERTAS`).** El bloqueo del boceto; el proveedor no cambia de estado.
- **Estado que cambió mientras tanto (`409` `ESTADO_NO_PERMITE_OPERACION`).** El bloqueo muestra el mensaje del servidor y la fila se recarga con su estado actual.
- **Sin permiso (`403`).** El mensaje que manda el servidor, sin ninguna cifra.
- **Proveedor que ya no existe (`404`).** Aviso y recarga de la lista.
````

Reconciliación de la pantalla 8 (F1 la hace con una sola sustitución). La viñeta *Proveedor* de «Acciones» de la pantalla 8, que hoy dice «No hay *baja* aparte: la única operación es `POST /proveedores/{id}/desactivacion`, que es una baja lógica (`activo = false`) y conserva órdenes e historial», pasa a:

````markdown
- *Proveedor*: solo activos; uno desactivado no aparece pero conserva su historial (HDU-004 esc. 12). El alta, la edición, la desactivación y la baja de proveedores viven en la [pantalla Proveedores](#2c--pantalla-proveedores) y no se dibujan aquí. Son **dos operaciones distintas**, y ninguna borra: `POST /proveedores/{proveedor_id}/desactivacion` pasa el proveedor a `DESACTIVADO` (sale del selector y conserva sus órdenes pendientes) y `POST /proveedores/{proveedor_id}/baja` lo pasa a `BAJA` (definitiva, solo sin órdenes `ABIERTA` ni `PARCIAL`) *(asumido, PA-24)*.
````

F1 también corrige, con una sustitución, la línea de la tabla de endpoints de la pantalla 8 que dice «`GET /proveedores` (activos)» solo si hace falta que diga `GET /proveedores?estado=ACTIVO`; **no es necesario**: el parámetro por omisión del borrador ya es `ACTIVO`. La ejecución no la toca.

Si D-6 se aprueba, F1 reescribe además en la pantalla 6 («Qué no es esta pantalla») la cita «*"No tienes permiso"*» por «el `mensaje` del servidor, sin cifras». Es la misma corrección que se acordó para obras en TKT-012a; si ya está hecha, F1 no hace nada.

## Plan de pruebas

Los nombres siguen el patrón de obras: `hdu004_escNN · <escenario>` para lo que cubre un escenario de la historia y `tkt032a_<tema> · …` para lo demás. Las pruebas de pantalla montan la aplicación en `/compras/proveedores` con MSW como servidor, igual que `PantallaObras.test.tsx`, y construyen las respuestas con los tipos generados (`satisfies`). La fábrica `proveedor(cambios)` se añade a `frontend/src/pruebas/cuerpos.ts` junto a `obra`.

| # | Caso | Tipo | Criterio que cubre | Escenario |
|---|---|---|---|---|
| TC-F01 | `ConflictoEnLinea` con un `RFC_DUPLICADO`: pinta «Proveedor existente CoPanel · XAXX010101000» y **no** el UUID ni la clave cruda | feliz | `CA-3` | `HDU-004 esc. 3` |
| TC-F02 | `PantallaBloqueo` con `PROVEEDOR_CON_ORDENES_ABIERTAS` y `detalle.ordenes`: tabla «Órdenes pendientes» con folio y estado de cada una, **no** JSON | feliz | `CA-8` | `HDU-004 esc. 12` |
| TC-F03 | La acción `DESACTIVAR_PROVEEDOR` se rotula «Desactivar el proveedor»; sin acciones, solo «Cerrar» | **rechazo** (lo que el servidor no manda no se pinta) | `CA-8` | `HDU-004 esc. 12` |
| TC-F04 | `FormularioCatalogo` con un campo `soloLectura`: el `<input>` es `readOnly`, conserva su valor y no se puede editar; los campos de texto, correo, fecha, casilla y desplegable de TKT-008c siguen igual | feliz | `CA-5`, `CA-R2` | — |
| TC-F05 | `esquemaAlta`: nombre y RFC obligatorios, RFC en mayúsculas con su patrón, `NUL` y 201 caracteres rechazados, `dia_corte` y `dia_pago` convertidos a entero 1 a 7, tope vacío → `null`, tope inválido (`"1e3"`, `"-5"`, `"٣"`, 5 decimales, 15 enteros) con mensaje | feliz · **rechazo** | `CA-4`, `CA-R4` | `HDU-004 esc. 2` |
| TC-F06 | `cambiosDe`: solo el nombre, solo el día de pago, solo el tope, el tope **vaciado** (envía `tope_consignacion: null`), ninguno (`null`), y tope `"300000.0000"` contra `"300000"` sin cambio (compara con `Decimal.eq`) | feliz · borde | `CA-5`, `CA-R4` | — |
| TC-F07 | `proveedoresOptions` envía `estado=ACTIVO` siempre, `q` solo si no está vacía, `pagina` y `tamano_pagina=50`; con «Todos», los tres estados repetidos (`estado=ACTIVO&estado=DESACTIVADO&estado=BAJA`, comprobado con `openapi-fetch` 0.17.0, E-1) | feliz | `CA-1` | `HDU-004 esc. 2` |
| TC-F08 | El tope `"99999999999999.9999"` viaja de formulario a cuerpo **idéntico y como cadena**; un cuerpo con `typeof tope_consignacion === "number"` falla la prueba | **rechazo** (dinero nunca flotante) | `CA-R4` | — |
| TC-F09 | `hdu004_esc02 · la lista ordenada con nombre, RFC, estado, corte y pago`: el corte y el pago se muestran por su nombre (`jueves`, `sábado`) | feliz | `CA-1` | `HDU-004 esc. 2` |
| TC-F10 | `tkt032a_lista · los cuatro estados`: cargando (esqueleto con etiqueta), vacío (con y sin invitación al `+` según el rol), con datos y error con `correlacion_id` y «Reintentar» que vuelve a pedir | feliz · **rechazo** | `CA-1` | — |
| TC-F11 | `tkt032a_lista · el filtro por estado`: por omisión «Activos»; elegir «Desactivados», «Dados de baja» y «Todos» vuelve a pedir con esos estados y a la página 1 | feliz | `CA-1` | — |
| TC-F12 | `tkt032a_lista · la búsqueda`: escribir y pulsar «Buscar» (o Enter) pide `q` y vuelve a la página 1; vaciarla quita `q` | feliz | `CA-1` | — |
| TC-F13 | `tkt032a_lista · la paginación`: «Página 1 de 3» con `total=120` y tamaño 50; «Siguiente» pide la 2; «Anterior» está inhabilitado en la 1 y «Siguiente» en la última; si tras una operación la página pedida queda vacía con `total` mayor que cero (se desactivó la única fila de la página 2), la pantalla vuelve a la última página con datos en lugar de pintar «vacío» | feliz · borde | `CA-1` | — |
| TC-F14 | `hdu004_esc12 · etiquetas de estado`: `Desactivado` y `Baja` se rotulan con texto distinto de `Activo` al filtrar (el *Should*) | feliz | `CA-1` | `HDU-004 esc. 12` |
| TC-F15 | `tkt032a_rol · Compras ve el + y las acciones de cada fila según el estado`: el `+` y, por fila, `ACTIVO` → Editar, Desactivar y Dar de baja; `DESACTIVADO` → Editar y Dar de baja; `BAJA` → ninguna | feliz | `CA-6`, `CA-7`, `CA-9` | `HDU-004 esc. 12` |
| TC-F16 | `tkt032a_rol · los otros cinco roles ven la lista y ninguna acción ni el +` (parametrizada con `DIRECCION_GENERAL`, `DIRECTOR_PROYECTOS`, `RESIDENTE`, `ALMACEN`, `ADMINISTRACION`) | **rechazo** | `CA-9` | — |
| TC-F17 | `CA-R1`: `/compras/proveedores` conserva su guarda (rol sin la sección → «No tienes permiso para esta sección»), su entrada de menú «Proveedores» y su título; sin sesión redirige al inicio de sesión | **regresión** | `CA-R1`, `CA-9` | — |
| TC-F18 | `hdu004_esc01 · el botón + abre el formulario con el foco en el nombre` | feliz | `CA-2` | `HDU-004 esc. 1` |
| TC-F19 | `hdu004_esc02 · alta con los valores por omisión`: precargados jueves y sábado; el cuerpo enviado lleva `dia_corte: 4` y `dia_pago: 6` como **enteros**, `tope_consignacion: null`; el formulario se cierra y la lista se vuelve a pedir | feliz | `CA-2` | `HDU-004 esc. 2` |
| TC-F20 | `hdu004_esc02 · alta con tope, corte y pago distintos`: el cuerpo lleva el tope como cadena y los días elegidos | feliz | `CA-2`, `CA-R4` | `HDU-004 esc. 2` |
| TC-F21 | `hdu004_esc03 · el RFC ya existe`: el formulario sigue abierto con lo capturado, el conflicto en línea con «Proveedor existente: nombre · RFC» y **ningún botón** (H-1); la lista no se vuelve a pedir | **rechazo** | `CA-3` | `HDU-004 esc. 3` |
| TC-F22 | `tkt032a_alta · 422 por campo` (parametrizada con `nombre`, `rfc`, `tope_consignacion`, `dia_corte` y `dia_pago`): el mensaje del servidor aparece junto a su campo con `aria-invalid` y el formulario sigue abierto; el formulario valida antes de enviar un nombre vacío y un RFC mal formado sin llamar al servidor | **rechazo** | `CA-4` | — |
| TC-F23 | `tkt032a_edicion · el RFC es de solo lectura`: abre «Editar proveedor» con los valores del proveedor, el tope sin cambiar de forma y el RFC no editable | feliz | `CA-5` | — |
| TC-F24 | `tkt032a_edicion · cambia el nombre y el día de pago`: el `PATCH` lleva **solo** `nombre` y `dia_pago`; el formulario se cierra y la lista muestra los datos nuevos | feliz | `CA-5` | — |
| TC-F25 | `tkt032a_edicion · sin cambios no hay petición`: guardar sin tocar nada cierra el formulario y no envía ningún `PATCH` | borde | `CA-5` | — |
| TC-F26 | `tkt032a_edicion · errores`: un `422` en `nombre` junto a su campo; un `404` muestra el aviso y **recarga la lista** | **rechazo** | `CA-5` | — |
| TC-F27 | `hdu004_esc12 · desactivar con motivo`: el diálogo pide el motivo; al confirmar envía `POST …/desactivacion` con `{ motivo }`; el proveedor sale de la lista por omisión y aparece al filtrar «Desactivados» | feliz | `CA-6` | `HDU-004 esc. 12` |
| TC-F28 | `hdu004_esc12 · desactivar sin motivo`: el botón de confirmar no envía y el campo señala el error | **rechazo** | `CA-6` | `HDU-004 esc. 12` |
| TC-F29 | `hdu004_esc13 · dar de baja sin órdenes pendientes`: envía `POST …/baja` con `{ motivo }`; el proveedor pasa a `BAJA`, deja de verse con el filtro por omisión y su fila, al filtrar «Dados de baja», no lleva ninguna acción | feliz | `CA-7` | `HDU-004 esc. 13` |
| TC-F30 | `hdu004_esc13 · dar de baja sin motivo`: no envía y el campo señala el error | **rechazo** | `CA-7` | `HDU-004 esc. 13` |
| TC-F31 | `hdu004_esc12 · baja con órdenes pendientes, proveedor ACTIVO`: el bloqueo muestra «No se puede completar» y `PROVEEDOR_CON_ORDENES_ABIERTAS`, el mensaje, las órdenes (folio y estado) y el botón «Desactivar el proveedor» **tomado de `acciones[]`**; el proveedor sigue `ACTIVO` en la lista. Comprueba el contrato completo de la respuesta de prueba: código, detalle y acción | **rechazo** | `CA-8` | `HDU-004 esc. 12` |
| TC-F32 | `hdu004_esc12 · desde el bloqueo se desactiva`: con **dos** proveedores en la lista (el bloqueado, que no es el primero, y otro), «Desactivar el proveedor» abre la captura de motivo de **ese** proveedor; al confirmar se desactiva, el bloqueo se cierra y la lista se recarga | feliz | `CA-8` | `HDU-004 esc. 12` |
| TC-F33 | `hdu004_esc12 · baja con órdenes pendientes, proveedor DESACTIVADO`: el bloqueo lista las órdenes y **no** ofrece desactivar (el servidor manda `acciones: []`); solo «Cerrar» | **rechazo** | `CA-8` | `HDU-004 esc. 12` |
| TC-F34 | `hdu004_esc12 · la pantalla no cablea la acción`: con un `PROVEEDOR_CON_ORDENES_ABIERTAS` simulado **sin** acciones y proveedor `ACTIVO`, no aparece «Desactivar el proveedor» | **rechazo** | `CA-8` | `HDU-004 esc. 12` |
| TC-F35 | `hdu004_esc12 · otro usuario cambió el estado`: `409` `ESTADO_NO_PERMITE_OPERACION` al confirmar «Desactivar» sobre la fila vieja → `PantallaBloqueo` con el mensaje del servidor, «Estado actual BAJA» y la lista vuelta a pedir con el estado actual | **rechazo** | `CA-10` | `HDU-004 esc. 12` |
| TC-F36 | `tkt032a_estado · 403, 404, espera de bloqueo y red`: el `403` pinta el `mensaje` del servidor sin cifras (D-6); el `404` avisa y recarga; la `CONCURRENCIA` muestra «Reintentar» que reabre la captura de motivo; un error de red muestra aviso sin caer | **rechazo** | `CA-9`, `CA-10` | — |
| TC-F37 | `tkt032a_contrato · cada ruta y cada cuerpo existen en servidor.ts`: ejecuta las cinco funciones de `proveedores.consultas.ts` contra MSW, registra método y plantilla de ruta de cada petición y comprueba que cada una aparece como clave de `paths` en `src/api/generado/servidor.ts` (leído como texto) con la operación del método; los cuerpos están atados por `satisfies` y `npm run typecheck` | contrato | `CA-R3` | — |
| TC-R2 | Las pruebas de `FormularioCatalogo`, `CapturaMotivo`, `ConfirmacionBaja`, `ConflictoEnLinea` y `PantallaBloqueo` de TKT-008c, **sin tocar una línea existente salvo las cuatro de D-10**: el test `tkt008_ca11_esc07 · la baja la rechaza el servidor` busca el botón por la clave cruda `DESACTIVAR_PROVEEDOR` y pasa a buscar «Desactivar el proveedor»; `VER_ORDENES_ABIERTAS` sigue cruda | regresión | `CA-R2` | — |
| TC-E1 | `e2e/proveedores.spec.ts` · `hdu004_esc02 · recorrido del catálogo`: Compras da de alta un proveedor `E2E-<8 hex>` con un RFC único por corrida que cumple el patrón (`EEE`, seis dígitos al azar y tres caracteres hexadecimales en mayúsculas; el patrón del servidor exige letras al inicio, así que un prefijo `E2E` daría `422`), lo ve en la lista, repite el alta con el mismo RFC y ve el conflicto con el proveedor existente (sin fila repetida), lo desactiva con motivo, deja de verse con el filtro por omisión y aparece al filtrar «Desactivados» | feliz · **rechazo** | `CA-11`, `CA-2`, `CA-3`, `CA-6` | `HDU-004 esc. 2, 3 y 12` |
| TC-E2 | `hdu004_esc12 · baja bloqueada por una orden PARCIAL real`: Compras da de alta otro proveedor, el spec siembra una orden `PARCIAL` contra su RFC con la ayuda `e2e/sembrar-orden.ts`, **Dar de baja** devuelve el `409` real con el folio de la orden y el botón «Desactivar el proveedor», que lo desactiva; el proveedor sigue sin estar en `BAJA` | **rechazo** | `CA-8`, `CA-11` | `HDU-004 esc. 12` |

**Mutación** (rutas de permiso y de estado de la interfaz). La tabla «mutante · test que cae» va en `impl.md`; el cliente no decide reglas de negocio, pero sí **qué ofrece**, y eso es lo que cada mutante estropea.

| Mutante | Cambio | Test que debe ponerse rojo |
|---|---|---|
| `M-1` | «Desactivar» también se ofrece a `DESACTIVADO` (se quita la guarda de estado) | TC-F15 |
| `M-2` | «Dar de baja» o «Editar» se ofrecen a `BAJA` | TC-F15 |
| `M-3` | Se ofrece alguna acción a un rol distinto de `COMPRAS` (el `+` incluido) | TC-F16 |
| `M-4` | `tope_consignacion` pasa por `Number` o por el formato de importe antes de enviarse | TC-F08, TC-F20 |
| `M-5` | El filtro por omisión deja de enviar `estado=ACTIVO` | TC-F07, TC-F11 |
| `M-6` | El bloqueo cablea el botón «Desactivar el proveedor» siempre, venga o no en `acciones[]` | TC-F33, TC-F34 |
| `M-7` | La acción del bloqueo desactiva al proveedor de la fila **anterior** en lugar del bloqueado (se pierde el proveedor objetivo) | TC-F32 |

## Entradas hostiles y datos inesperados

Todo rechazo de forma lo decide el servidor; el cliente valida antes de enviar solo por cortesía y el `422` manda (`CA-4`). La columna «Test» dice dónde queda probado.

| Campo | Qué se rechaza | Código | Test |
|---|---|---|---|
| `nombre` | Vacío o solo espacios; más de 200 caracteres; carácter `NUL` (el servidor responde `422`, el cliente lo avisa antes) | `422` | TC-F05, TC-F22 |
| `rfc` | Vacío; fuera del patrón `^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$` tras recortar y pasar a mayúsculas (el servidor hace la misma normalización); minúsculas, dígitos no ASCII o salto de línea | `422` | TC-F05, TC-F22 |
| `rfc` ya existente (incluido el de un proveedor `BAJA`, que conserva su RFC) | El alta duplicada | `409` `RFC_DUPLICADO` | TC-F21, TC-E1 |
| `tope_consignacion` | Exponente, signo, más de 14 enteros o más de 4 decimales, dígitos no ASCII, número JSON en lugar de cadena | `422` | TC-F05, TC-F08, TC-F22 |
| `dia_corte`, `dia_pago` | Fuera de 1 a 7; el desplegable solo ofrece siete valores, pero el servidor lo comprueba | `422` | TC-F22 |
| `motivo` | Vacío o solo espacios (cliente y servidor); más de 2000 caracteres (el cliente corta el envío) | `422` | TC-F28, TC-F30 |
| `q` | `NUL` o más de 200 caracteres: la búsqueda recorta y el servidor rechaza con `422`, que se pinta como el aviso de error de la lista | `422` | TC-F10 |
| Respuesta con `tipo` desconocido o cuerpo que no es JSON | `normalizarError` la convierte en `GENERICO`; la pantalla pinta el aviso con el mensaje por omisión, no cae | — | TC-F36 |

## Comprobaciones que el diseño afirma y aún no se ejecutaron

| # | Afirmación | Evidencia | Fila que la comprueba |
|---|---|---|---|
| E-1 | `openapi-fetch` serializa el parámetro repetible `estado` como `estado=A&estado=B` | **Ejecutado al diseñar** con `createClient` de `openapi-fetch` 0.17.0 y un `fetch` simulado: `http://x/p?estado=ACTIVO&estado=BAJA&q=a%20b&pagina=1` | TC-F07 |
| E-2 | La orden que siembra `sembrar_orden_compra` con un renglón `("10.0000", "4.0000")` es `PARCIAL` y no `ABIERTA` | **Comprobada por lectura** (`revisor-impacto`): `compras/dominio/orden_compra.py:39-46` da `PARCIAL` con saldo y algo recibido; **sin ejecutar** de punta a punta | TC-E2 |
| E-3 | `raw_connection().driver_connection` de un motor de SQLAlchemy con `psycopg` entrega la conexión `psycopg` que `sembrar_orden_compra` espera, y su `commit()` confirma | **Comprobada por lectura**: `test_tkt029b_ordenes_pendientes.py:368` usa `sesion.connection().connection.driver_connection`; **sin ejecutar** el `commit()` | F10 |
| E-4 | El `<input readOnly>` registrado con React Hook Form **sí** envía su valor en `handleSubmit` (un `disabled` no) | Comportamiento documentado de React Hook Form (Context7); **sin ejecutar** | TC-F04 |
| E-5 | Zod 4 admite `.transform` con `ctx.addIssue` y `z.NEVER` en esquemas de campo, como el de obras | Ya en uso en `obras.formulario.ts` | TC-F05 |
| E-6 | `CapturaMotivo` entrega un `409` a `alRechazo` y deja la pantalla decidir; un `422` con entradas lo conserva | Leído en `CapturaMotivo.tsx` (`rechazar`); probado por `CapturaMotivo.test.tsx` | TC-F27 a TC-F36 |
| E-7 | `PantallaBloqueo` con `acciones: []` pinta solo «Cerrar» | Leído en `BotonesAcciones.tsx` | TC-F03, TC-F33 |

Las que quedan «sin ejecutar» se comprueban en su fila **antes de construir encima**; ninguna se presenta como hecho.

## Impacto

Resultado de `revisor-impacto` (2026-11-17): **diseño incompleto en su primera versión, sin frontera cruzada** (`uv run lint-imports`: 16 contratos en verde; `herramientas/` no entra en import-linter, que solo analiza `cimenta`, `tipos_base` y `trabajos`, pero sí la cubren `ruff` y `mypy`). Sus ocho hallazgos están incorporados:

1. **Bloqueante.** `FormularioCatalogo.test.tsx:443-456` busca el botón por la clave cruda `DESACTIVAR_PROVEEDOR`, que la etiqueta nueva rompe. Declarado como D-10, en F2 y en TC-R2.
2. **Mayor.** TKT-012b añade también `soloLectura` (su fila B1). Fila de coordinación abajo y nota en F3.
3. **Mayor.** Archivos compartidos con 012b: fila de coordinación abajo.
4. **Mayor.** El sembrador no cubría `tipo_partida_id`, `insumo_id`, la búsqueda por RFC, el folio único ni el `commit`. «Detalle del sembrador de F10».
5. **Menor.** `estado_actual` del `409` llegaba como clave cruda. Rótulo nuevo en F2 y aserción en TC-F35.
6. **Menor.** Las pruebas de TKT-008c son 24, no 21. Corregido.
7. **Menor.** La obra de humo se comparte con `linea-base.spec`. Fila de riesgo abajo.
8. **Menor.** Docstring y `docs/arranque-local.md` decididos en el detalle del sembrador.

Lo que el diseño ya identificaba:

| Qué se toca | Quién depende | Riesgo | Mitigación |
|---|---|---|---|
| `etiquetas.ts` (`TABLAS_DETALLE`, `CLAVES_DETALLE`, `CLAVES_OCULTAS`, `ETIQUETAS_ACCION`) | `PantallaBloqueo`, `ConflictoEnLinea`, `FormularioCatalogo`, las pantallas de obras y de línea base | Medio: la tabla `ordenes` cambia cómo se pinta ese detalle, y la prueba de TKT-008c del conflicto con órdenes lo busca por texto | F2 corre las cinco suites de bloqueo y formulario sin modificar una línea existente (`CA-R2`); un `ordenes` en una pantalla que no sea la de proveedores no existe hoy |
| `FormularioCatalogo.tsx` | Alta de obras de TKT-012a; las pruebas de TKT-008c; TKT-012b (edición de obras, en diseño) | Medio: el tipo `CampoTextoCatalogo` gana una propiedad **opcional** | La propiedad es opcional y por omisión es falsa; F3 corre las 24 pruebas sin modificar; la pantalla de obras y su prueba corren en F3 |
| `rutas.tsx` de `proveedores` | `app/rutas.tsx`, `Armazon`, humo | Bajo: misma ruta y misma guarda | TC-F17; las tres de `humo.spec.ts` corren en F10 |
| `frontend/src/pruebas/cuerpos.ts` (fábrica `proveedor`) | Todas las pruebas de pantalla | Bajo: solo se añade una función | F5 |
| `backend/herramientas/semilla_orden_proveedor_local.py` y el docstring de `soporte_tkt029b_ordenes.py` (H-2) | `import-linter` (no analiza `herramientas/`), `ruff`, `mypy`, la suite de TKT-029b que importa la ayuda | Bajo: archivo nuevo de apoyo de pruebas; el docstring solo gana una frase | F10 corre `lint-imports`, `ruff`, `mypy`, `verificar_float` y `uv run pytest tests/test_tkt029b_ordenes_pendientes.py tests/test_tkt029b_api_baja.py` |
| `preparacion-global.ts` | Todos los E2E | Ninguno: **no se modifica** | La siembra de la orden la hace el spec de proveedores con `e2e/sembrar-orden.ts`, justo después de dar de alta al proveedor; el spec reutiliza la obra `CIMENTA_HUMO_LB_OBRA_ID` y el usuario de Compras que la preparación ya siembra, así que ningún otro spec (obras, línea base, humo) cambia |
| Base de humo acumulativa | `e2e/proveedores.spec.ts` | Bajo: con unas 50 corridas, un proveedor nuevo puede salirse de la primera página de 50 | RFC y nombre con prefijo `E2E`, y el spec **busca por RFC** con el campo de búsqueda antes de buscar la fila; documentado en el comentario del spec |
| `PantallaObras.tsx` | TKT-012b modifica la pantalla en paralelo | Alto si se toca | **Este ticket no la toca**: se copian los estados de lista en `estados-lista.tsx` (ver escalera) |
| **Coordinación con TKT-012b** (diseño paralelo, `sdd/tickets/tkt-012b/design.md`) | Archivos que ambos tickets tocan: `FormularioCatalogo.tsx` (**ambos añaden `soloLectura`**, 012b en su fila B1), `docs/08-wireframes.md` (aquí la 2c, allá la 2b, bloques contiguos), `docs/05-tickets-trabajo.md`. Probables y sin confirmar: `etiquetas.ts` (012b necesitará rótulos de `SUSPENDER_OBRA`, `CERRAR_OBRA` y de su detalle), `frontend/src/api/generado/servidor.ts` (012b regenera tipos) y `e2e/preparacion-global.ts` (012b B5; este ticket solo lee `CIMENTA_HUMO_LB_OBRA_ID`) | Medio: conflictos textuales y una propiedad introducida dos veces | **El primer ticket que se ejecute introduce `soloLectura`**, con el mismo nombre y la misma semántica (`readOnly` y `aria-readonly`); el segundo elimina su fila (F3 aquí, B1 allá) y su prueba, y se rebasa. Las ediciones de `etiquetas.ts` de ambos son aditivas y van en bloques distintos. Se acuerda el orden de fusión al aprobar los dos diseños |
| La obra de humo `CIMENTA_HUMO_LB_OBRA_ID` | `linea-base.spec.ts` la congela; este spec cuelga una requisición y una orden de ella | Bajo: `workers: 1` y orden alfabético hacen que `proveedores.spec.ts` corra después | Si TKT-012b cuenta el historial de una obra al suspenderla o cerrarla, esa obra de humo lo tendrá; ninguna prueba de 012b la usa. Se anota en el comentario del spec |

**Fronteras entre módulos:** No. El cambio es de frontend y de una herramienta que ya existe en `backend/herramientas/`; no importa ningún módulo de `cimenta/` por fuera de su interfaz. El módulo `proveedores` del cliente solo importa de `compartido/` y de `api/`.

## Documentación afectada

| Documento | Qué cambia |
|---|---|
| `docs/08-wireframes.md` | Subsección «2c · Pantalla Proveedores» y la viñeta *Proveedor* de la pantalla 8 reconciliada con la baja (F1, **primera fila**). Si D-6 se aprueba, la cita «No tienes permiso» de la pantalla 6 |
| `docs/05-tickets-trabajo.md` | La partición de TKT-032 ya está registrada en el árbol de trabajo; `/sdd-completar` la confirma y marca TKT-032a |
| `docs/04-historias-usuario.md` | Sin cambios: los escenarios 1, 2, 3, 12 y 13 ya existen; las pruebas del cliente llevan su `hdu004_escNN` |
| `docs/arranque-local.md` | Una línea si el sembrador de la orden se documenta junto a los de humo (la ejecución decide al ver cómo se documentan los demás) |
| `sdd/tickets/tkt-032a/_index.md` | Enlace a este diseño y estado |
| `docs/api/openapi.yaml`, `docs/07-especificacion-api.md`, `docs/03-modelo-datos.md`, `docs/02-arquitectura.md`, `CLAUDE.md` | Sin cambios: no hay ruta, campo, esquema, módulo ni invariante nuevos |

## ¿Merece ADR?

No. Todas las decisiones reutilizan una ya registrada o son locales a una pantalla: el patrón de obras de TKT-012a, los componentes de TKT-008c, la sesión con estado (`ADR-014`), el dinero como cadena y el contrato de error. La única opción descartada de peso —los botones de estado dentro del formulario de edición— queda explicada en la escalera y en D-8, y no es de las que alguien nuevo cuestionaría en el repositorio.

## Pasada adversarial

Aplicada el 2026-11-17 con la skill `abogado-del-diablo` (modo A, «diseñar») sobre este diseño, después de la pasada de impacto. Es una pasada propia, no la de un subagente independiente.

| # | Severidad | Objeción | Acción tomada |
|---|---|---|---|
| 1 | Alta | **La spec pide una acción que el contrato no tiene.** `CA-3` exige «la acción de verlo» y el backend responde `acciones=()`; si el diseño la inventara, el cliente cablearía un botón de negocio contra la regla del bloqueo | H-1: no se diseña; el conflicto pinta al proveedor existente sin botón y la salida recomendada reescribe `CA-3` |
| 2 | Alta | **El E2E de `CA-8` obliga a tocar `backend/`** y la spec dice «ningún cambio al backend» | H-2: se declara y se acota a un sembrador local de apoyo de pruebas que niega bases no locales; la persona dueña confirma la lectura de la Definition of Done |
| 3 | Alta | **Una página puede quedar vacía tras desactivar o dar de baja**: la única fila de la página 2 sale del filtro y la pantalla pintaría «vacío» con `total` mayor que cero | La pantalla pide la última página con datos; TC-F13 lo prueba |
| 4 | Media | **«Editar» con la baja** (`CA-7`: ninguna acción más) y un servidor que no comprueba el estado al editar: sin guarda en la interfaz, un `DESACTIVADO` o `BAJA` se edita | D-7 y el mutante `M-2`; el control real de un `BAJA` sigue en el servidor (D-3 de TKT-029a), anotado |
| 5 | Media | **Vaciar el tope no se podía distinguir de «sin cambio»** al enviar solo lo cambiado | `cambiosDe` envía `tope_consignacion: null` cuando se vacía; caso añadido a TC-F06 |
| 6 | Media | **`M-7` solo cae si la lista tiene dos proveedores** y el bloqueado no es el primero | TC-F32 lo exige |
| 7 | Baja | **Un rojo falso**: TC-F04 y la fila F3 desaparecen si 012b introduce `soloLectura` antes | Fila de coordinación y nota en F3 |

Veredicto: siete objeciones sustantivas; ninguna rompe un invariante registrado. Quedan abiertas para la persona dueña las que no puede cerrar el diseño: D-6 a D-10, H-1 y H-2.

## Riesgos

| Riesgo | Probabilidad | Impacto | Qué se hace |
|---|---|---|---|
| Plazo de la entrega 3: la fecha vigente la fija la persona dueña y el diseño no la asume | Media | Medio | Dos entregas; la a deja el catálogo en lectura y el alta operativos aunque la b se retrase |
| H-1: la persona dueña quiere el botón «ver al existente» y exige backend | Media | Bajo | Se registra como ticket futuro de backend; este ticket no lo bloquea |
| H-2: no se acepta el sembrador como apoyo de pruebas | Baja | Medio | `CA-8` queda cubierto por MSW (TC-F31 a TC-F34) y TC-E2 se retira; la spec lo declara en el DoD |
| E-2 y E-3 resultan falsas en F10 | Media | Bajo | Se descubren en el primer paso de F10, antes del spec; el sembrador usa otra forma de obtener la conexión o otra cantidad |
| Conflicto de edición con TKT-012b en `FormularioCatalogo.tsx` | Media | Medio | F3 añade una propiedad opcional y dos líneas; si 012b toca el mismo bloque, se resuelve al rebasar. Esta sesión no comparte archivos con 012b salvo ese |
| Choques de archivo con TKT-012b al ejecutar: ambos tickets tienen una fila que edita `docs/08-wireframes.md` (F1 aquí, el boceto de edición de obras allá) y pueden tocar `FormularioCatalogo.tsx` y `pruebas/cuerpos.ts` | Media | Medio | Las dos ramas salen de `Produccion` y van a PR distintos: la segunda en fusionarse rebasa y resuelve a mano; las ediciones de este ticket son aditivas (una subsección nueva, una propiedad opcional, una fábrica nueva) |
| Duplicación de `EsqueletoLista` y `AvisoErrorLista` con obras | Alta | Bajo | Ticket de refactor sugerido tras fusionar 032a y 012b: extraer a `compartido/componentes/lista/` y usarlos en ambas pantallas |
| Un proveedor `DESACTIVADO` no puede volver a `ACTIVO` y Compras lo espera | Media | Medio | El texto del diálogo de desactivar lo dice; `PA-24` sigue abierta y ya está en los tickets futuros del hub |
| `enteroNoNegativo` convierte `"4"` en `4` pero un cambio futuro de su regex lo rompería para los días | Baja | Bajo | TC-F05 fija la conversión de los siete valores |

## Ajustes de la ejecución

Se llena durante `/sdd-ejecutar` y `/sdd-revisar`.

| Fecha | Fila | Ajuste | Motivo |
|---|---|---|---|
| 2026-11-17 | F3 | La fila se elimina y TC-F04 no se escribe. `FormularioCatalogo` ya trae `soloLectura` desde TKT-012b (PR #80), con `readOnly` en los campos de texto y con una semántica adicional: el campo de solo lectura **se quita del cuerpo que entrega `alGuardar`** (`delete enviado[campo.nombre]`). | El diseño preveía este caso en la fila de coordinación con TKT-012b («el segundo elimina su fila»). La semántica adicional no estorba: el RFC no viaja en el `PATCH` de todos modos, porque `cambiosDe` solo envía lo cambiado. TC-F23 sigue comprobando que el RFC se ve y no se edita. |
| 2026-11-18 | F7 | Una prueba de la fila se corrigió en el ciclo de la fila: en el caso `ACTIVO` del bloque D-7 elegía «viernes», que era el día de pago que ya tenía el proveedor de la prueba, así que no había cambio y `cambiosDe` no enviaba nada. El tester la cambió a «lunes» y esperó `{ dia_pago: 1 }`. | La devolvió el desarrollador por imposible y la corrigió el tester, no el desarrollador. Anotado en «Tests devueltos al tester» de `impl.md`. |
| 2026-11-18 | F8 | El refactor extrajo `TablaProveedores.tsx` (tabla, `accionesDe`, etiquetas de acción y de estado, `nombreDeDia`) de la pantalla, que superaba las 260 líneas. El diálogo de confirmar la desactivación se rotula «Confirmar desactivación» (el boceto solo fija «Confirmar baja»). El aviso de bloqueo del alta y de la edición no se sustituye por `PantallaBloqueo`: `POST /proveedores` y `PATCH /proveedores/{proveedor_id}` pueden responder `409` `CONCURRENCIA` (`BLOQUEO_VENCIDO`) si vence el bloqueo; el alta y la edición cierran el formulario y avisan en la cabecera con el mensaje del servidor y su referencia, y lo capturado se pierde. La persona dueña decidió el 2026-11-18 dejarlo así: no se ofrece «Reintentar». | Un archivo más de producción dentro del módulo de la pantalla; sin cambio de comportamiento. |
| 2026-11-18 | F10 | El RFC de prueba lleva el prefijo `EEE` y no `E2E`. El nombre sí conserva `E2E-<8 hex>`. El sembrador imprime además `FOLIO=<folio>` antes de `ORDEN_ID=<uuid>`, y comprueba que la obra existe antes de insertar. | El patrón del servidor (`^[A-ZÑ&]{3,4}[0-9]{6}[A-Z0-9]{3}$`) exige letras al inicio. La línea `FOLIO=` deja que la ayuda del E2E compare el folio exacto. |
| 2026-11-18 | F8 | `PantallaProveedores.tsx` extrajo `useOperacionDeEstado` (`useOperacionDeEstado.ts`) y fusionó los dos avisos de bloqueo del alta y de la edición en `avisarYCerrar`. | Hallazgos F002 y F005 de `auditor-codigo`: quitar la duplicación y bajar la pantalla de tamaño; sin cambio de comportamiento. |
