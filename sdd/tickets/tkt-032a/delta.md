# Delta · TKT-032a · Pantalla del catálogo de proveedores

> [← index](_index.md) | [← impl](impl.md)

El delta no repite la implementación: declara **qué cambió en el sistema** respecto a como estaba antes. El ticket se ejecutó en dos entregas, acumuladas en la rama `tkt-032a-pantalla-proveedores` y fusionadas en un solo PR:

- **Entrega a (F1 a F6, sin F3):** el boceto de la pantalla y la reconciliación de la baja en `docs/08-wireframes.md`, las etiquetas del bloqueo para proveedores, las consultas y los esquemas del formulario, la lista con filtro, búsqueda y paginación, y el alta.
- **Entrega b (F7 a F10):** la edición, desactivar y dar de baja con sus bloqueos, la prueba de contrato y el recorrido de extremo a extremo con un sembrador local de una orden `PARCIAL`.

## Añadido

| Qué | Dónde | Para qué |
|---|---|---|
| Pantalla del catálogo de proveedores | `frontend/src/modulos/proveedores/catalogo/PantallaProveedores.tsx` y `TablaProveedores.tsx` | Lista ordenada de proveedores con nombre, RFC, estado, día de corte y de pago, con filtro por estado, búsqueda por nombre o RFC y paginación de 50 en 50. Solo Compras ve el `+` y las acciones por fila |
| Consultas y mutaciones del catálogo | `proveedores.consultas.ts` | Una sola puerta, sin lanzar, a las cinco rutas ya publicadas de `/api/v1/proveedores`; `TAMANO_PAGINA` y `totalDePaginas` |
| Esquemas y campos del formulario | `proveedores.formulario.ts` | Validación de cortesía del alta y la edición (el servidor manda), tope de consignación siempre como cadena, días de corte y pago de 1 a 7, y `cambiosDe`, que envía solo lo que cambió |
| Estado de las operaciones de baja y desactivación | `useOperacionDeEstado.ts` | Guarda el proveedor que se intentó operar y el bloqueo con su error, para que la acción «Desactivar el proveedor» actúe sobre ese proveedor |
| Estados de lista | `estados-lista.tsx` | Esqueleto, aviso de error con referencia y estado vacío con invitación al `+` |
| Pruebas del cliente | Ocho archivos nuevos en `frontend/src/modulos/proveedores/catalogo/` (esquemas, consultas, lista, ruta, alta, edición, estado y contrato) y pruebas añadidas en `PantallaBloqueo.test.tsx` y `ConflictoEnLinea.test.tsx` | La suite del cliente termina en 931 pruebas, todas en verde; cada regla implicada tiene su escenario de rechazo con el contrato de error completo |
| Recorrido de extremo a extremo | `frontend/e2e/proveedores.spec.ts` y `sembrar-orden.ts` | Alta, RFC repetido, desactivar, y la baja bloqueada por una orden `PARCIAL` real |
| Sembrador local de apoyo de pruebas | `backend/herramientas/semilla_orden_proveedor_local.py` | Siembra una orden `PARCIAL` contra un proveedor ya dado de alta, solo en la base local (H-2) |
| Boceto «2c · Pantalla Proveedores» | `docs/08-wireframes.md` | Dibuja la lista, el alta, la edición, el conflicto, la captura de motivo y el bloqueo de la baja |
| Evidencia del ciclo TDD | `sdd/tickets/tkt-032a/rojo/*.txt` | Salida literal de cada rojo y del verde del extremo a extremo |

## Modificado

| Qué | Dónde | Antes → después |
|---|---|---|
| Ruta de la sección «Proveedores» | `frontend/src/modulos/proveedores/rutas.tsx` | Marcador «Esta sección aún no está disponible» → `PantallaProveedores`; misma ruta `/compras/proveedores` y misma guarda |
| Rótulos del bloqueo | `frontend/src/compartido/componentes/bloqueo/etiquetas.ts` | Las órdenes pendientes salían como JSON crudo, el proveedor existente como clave desconocida y la acción como `DESACTIVAR_PROVEEDOR` → tabla «Órdenes pendientes», «Proveedor existente», «Estado actual» y «Desactivar el proveedor» |
| Prueba de TKT-008c | `frontend/src/compartido/formularios/FormularioCatalogo.test.tsx` | Cuatro líneas buscaban el botón por la clave cruda `DESACTIVAR_PROVEEDOR` → lo buscan por «Desactivar el proveedor» (D-10, aprobado) |
| Fábricas de pruebas | `frontend/src/pruebas/cuerpos.ts` | Sin fábrica de proveedor → `proveedor(cambios)` |
| Wireframes | `docs/08-wireframes.md` | La pantalla 8 decía que no había baja aparte → distingue desactivar y dar de baja y remite a 2c; la baja terminal se marca `(asumido, PA-24)`; el `403` de la pantalla 6 es el mensaje del servidor; fila nueva en §13 |
| Arranque local y ayuda de pruebas | `docs/arranque-local.md` y `backend/herramientas/soporte_tkt029b_ordenes.py` | Sin el sembrador → un párrafo con el sembrador; el docstring dice que solo la usan las pruebas y los sembradores locales |
| Plan de tickets | `docs/05-tickets-trabajo.md` | TKT-032 partido en 032a y 032b, y la frase de TKT-029 sobre la pantalla del catálogo apunta a TKT-032a |

## Eliminado

| Qué | Dónde | Por qué era seguro quitarlo |
|---|---|---|
| Marcador de la sección «Proveedores» | `rutas.tsx` | La pantalla lo sustituye con la misma ruta; las nueve pruebas de la guarda y del menú (TC-F17) siguen en verde |
| La fila F3 del diseño (`soloLectura` en `FormularioCatalogo`) | `design.md` | TKT-012b ya la había introducido; no se escribió ni su prueba |

## Comportamiento observable nuevo

- Las seis personas con rol ven en `/compras/proveedores` la lista de proveedores (por omisión, solo los activos), con filtro por estado (Activos, Desactivados, Dados de baja, Todos), búsqueda y paginación.
- Solo Compras puede dar de alta (con jueves y sábado por omisión), editar (el RFC no se cambia), desactivar y dar de baja, con un motivo obligatorio en las dos últimas.
- Un RFC repetido muestra al proveedor existente en línea y no crea nada. No hay botón de ver al existente: el contrato no lo ofrece (H-1).
- Dar de baja a un proveedor con órdenes pendientes muestra el bloqueo con sus folios y estados; si el proveedor está activo, ofrece «Desactivar el proveedor». Con el proveedor ya desactivado solo queda «Cerrar».
- Un `409` por estado que cambió en otra sesión muestra el mensaje del servidor y recarga la lista. Un `409` de concurrencia en el alta o la edición cierra el formulario y avisa en la cabecera; lo capturado se pierde (decisión de la persona dueña, 2026-11-18).

## Contrato público tocado

| Superficie | Cambio | ¿Rompe compatibilidad? |
|---|---|---|
| Endpoints, DTO, tipos generados, esquema | Ninguno: la pantalla consume las cinco rutas ya publicadas; `tipos:verificar` da «Tipos al día» y `docs/api/openapi.yaml` no cambia | No |
| `herramientas.semilla_orden_proveedor_local` | Sembrador nuevo con tres variables de entorno y dos líneas de salida (`FOLIO=` y `ORDEN_ID=`); es de apoyo de pruebas y no es parte del contrato del producto | No |

## Decisiones (ADR)

Ninguna merece ADR: todas reutilizan una decisión registrada (el patrón de obras de TKT-012a, los componentes de TKT-008c, la sesión con estado, el dinero como cadena y el contrato de error) o son locales a la pantalla. La opción descartada de más peso, los botones de estado dentro del formulario de edición (en lugar de la ranura `baja` de `FormularioCatalogo`), queda explicada en la escalera y en la decisión D-8 de `design.md`, y es local a esta pantalla: ningún otro módulo la comparte ni depende de ella. Si la persona dueña prefiere un ADR, se abre aparte.

## Aprendizajes

| Aprendizaje | Evidencia | Dónde aplica |
|---|---|---|
| Una prueba de contrato sobre funciones que ya existen nace en verde, y su valor se demuestra con mutantes de ruta, método y cuerpo, no con un rojo | `rojo/fila-9.txt`: seis pruebas en verde y cinco mutantes que la ponen en rojo | Toda fila de «prueba de contrato» posterior a la implementación de la capa que prueba |
| El `409 CONCURRENCIA` es alcanzable en cualquier escritura con bloqueo pesimista, aunque el contrato del diseño no lo mencione para el alta y la edición | `backend/cimenta/proveedores/aplicacion/proveedores.py` (`_traducir_concurrencia`) y la respuesta `Conflicto` del borrador | Cualquier pantalla de alta o edición de un módulo con bloqueo |
| Mutar sobre una copia que se resincroniza con `robocopy /MIR` borra el mutante: hay que mutar en una carpeta aparte | Mutantes de las revisiones | Cualquier prueba de mutación que use el script de la copia |
| El RFC de prueba debe cumplir el patrón del servidor, que exige letras al inicio: el prefijo `E2E…` da `422` | El spec usa `EEE` + 6 dígitos + 3 hex | Datos de prueba de cualquier campo con patrón |
| La baja terminal del proveedor es un supuesto de `PA-24` y toda frase que la afirme lleva `(asumido, PA-24)` | `auditor-docs`, hallazgo F001 de la entrega a | Documentación y boceto de la pantalla |

## Observaciones para `_evolucion.md`

Fricción del **proceso**, no del producto. Son las nueve filas de `sdd/_evolucion.md` con fecha 2026-11-18 y ticket TKT-032a; la tabla siguiente es esa copia, con el mismo tema y la misma severidad.

| Tema | Observación | Severidad |
|---|---|---|
| `herramienta` | Un `npm ci` lanzado por un agente tester falló con `EPERM` porque un servidor de desarrollo de la persona dueña tenía tomado un binario nativo, y dejó `frontend/node_modules` incompleto durante todo el ticket: todo el cliente se probó sobre una copia sincronizada con `robocopy`, y el arreglo quedó como acción de la persona dueña. El encargo no prohibía `npm ci` sobre un `node_modules` existente ni pedía comprobar procesos antes | Media |
| `comando` | El extremo a extremo no arrancaba sobre la copia sincronizada porque `playwright.config.ts` busca `../.env` desde `backend/` y la unión de directorios conserva la ruta lógica: hubo que copiar el `.env` local al scratchpad sin leerlo y borrarlo después. Falta una forma documentada de correr el extremo a extremo cuando `node_modules` del repositorio no sirve | Media |
| `guardrail` | La evidencia del rojo (`rojo/*.txt`) se guardó con rutas absolutas que contenían el nombre de usuario del sistema; lo detectó `auditor-seguridad` en la revisión de la entrega a. El encargo al tester no pedía sustituir el prefijo local al guardar la salida, y el saneado se hizo a mano | Media |
| `comando` | El diseño afirmó que el alta y la edición «no declaran ningún `409` de regla ni `CONCURRENCIA`»: falso para `POST` y `PATCH`, cuyo caso de uso corre bajo `_traducir_concurrencia`. Lo destapó `auditor-codigo` en la revisión de la entrega b, con una rama sin prueba, y no `/sdd-disenar` ni `revisor-impacto`. Otra afirmación del diseño sin comprobar contra el contrato real | Media |
| `documentación` | El diseño fijó un prefijo `E2E` para el RFC de prueba sin comprobarlo contra el patrón del servidor (`[A-ZÑ&]{3,4}…`), que exige letras al inicio; lo encontró el tester al escribir el extremo a extremo. Los datos de prueba con patrón no aparecían en la tabla de comprobaciones del diseño | Baja |
| `plantilla` | Una fila de «prueba de contrato» (F9) escrita después de la capa que prueba nace en verde, y la plantilla de `impl.md` y el paso 2a asumen un rojo por fila. Se resolvió con cinco mutantes de ruta, método y cuerpo y una nota, pero no hay un lugar fijo para declarar «nace en verde» | Baja |
| `guardrail` | Mutar sobre la copia que el script de ejecución resincroniza con `robocopy /MIR` borra el mutante en la siguiente corrida; hubo que montar una segunda copia en el scratchpad con una unión al `node_modules`. El protocolo de mutación del tester no nombra este caso | Baja |
| `comando` | El script de ejecución del cliente apuntaba a una ruta de scratchpad fija; al cambiar la sesión y su scratchpad, la ruta fija quedó desfasada de la que anunciaba el entorno | Baja |
| `comando` | **Remedio que funcionó:** la fila de coordinación con TKT-012b del diseño («el segundo elimina su fila») permitió eliminar F3 sin discusión cuando 012b ya había fusionado `soloLectura`, y la devolución de un test imposible por el desarrollador (F7) se resolvió en un solo ciclo con el tester | Baja |

## Deuda que queda abierta

| Qué | Por qué se dejó | Ticket sugerido |
|---|---|---|
| Acción de ver al proveedor existente en el `409` `RFC_DUPLICADO` | El contrato no la ofrece; requiere backend y `openapi.yaml` (H-1) | `VER_PROVEEDOR` |
| Reactivar un proveedor desactivado o dado de baja | No existe esa operación; `PA-24` sigue abierta | Ticket futuro, tras `PA-24` |
| Extraer `EsqueletoLista`, `AvisoErrorLista` y la copia de `esBloqueo` a `compartido/` | Duplicado a propósito mientras TKT-012b modificaba obras; ahora está fusionado | Ticket de refactor |
| Publicar la normalización del RFC en `proveedores.interfaz` | El sembrador local la importa del dominio, como los demás sembradores de `herramientas/`; `interfaz.py` sigue vacía | Cuando otro código la necesite |
| `exigir_base_local` acepta un túnel `localhost` hacia una base remota | Riesgo heredado de todos los sembradores | Ticket de revisión de las herramientas de siembra (por abrir) |
| `frontend/node_modules` incompleto en el equipo de la persona dueña | Lo ocupa su servidor de desarrollo | Acción de la persona dueña: parar `npm run dev` y ejecutar `npm ci` |
| Hallazgos del `code-review` previo al PR, de severidad baja o media: la edición compara contra la foto del proveedor al abrir el diálogo y no contra el dato vigente; `alAccion` vacío en el alta y la edición; la lista sin `placeholderData` parpadea al paginar; lógica de aviso y `esBloqueo` duplicada con `FormularioCatalogo`; `buscarPorRfc` del E2E puede esperar una petición que sirve la caché; `rollback()` del sembrador puede enmascarar el error original; `SalidaEdicion` a mano en lugar de `z.output`; tabla sin nombre accesible; el hijo del E2E hereda todo `process.env`; `rojo/fila-7.txt` con 7 687 líneas de volcado del DOM | Ninguno rompe un criterio; arreglarlos amplía el alcance y toca componentes compartidos | Ticket de refactor y accesibilidad de la pantalla de proveedores |
| Consulta proveedor × obra, emisión y cancelación de órdenes | Dependen de TKT-030 y TKT-031 | TKT-032b |

## Pull request

**Título:** `TKT-032a · Pantalla del catálogo de proveedores`
**Origen:** `agent`: el código lo escribieron agentes; la persona dueña aprobó el diseño, tomó las decisiones D-1 a D-10, H-1 y H-2 y aprobará la fusión sobre un resumen.
**Cuerpo:** qué (la pantalla del catálogo de proveedores, en dos entregas), por qué (la prueba manual de la entrega 3 mostró que el catálogo no tenía pantalla), criterios cubiertos (`CA-1` a `CA-11` y `CA-R1` a `CA-R4`) y cómo verificarlo (`npm test`, `npm run e2e` con la base y el backend locales, `npm run tipos:verificar`).

**Fusión con omisión:** el registro no va en este archivo, porque `delta.md` se escribe antes de fusionar. Va en un comentario del PR que el orquestador deja justo después de fusionar, solo con la aprobación explícita de la persona dueña en la sesión.
