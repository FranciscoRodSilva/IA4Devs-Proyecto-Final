# Impl · TKT-032a · Pantalla del catálogo de proveedores

> [← index](_index.md) | [← design](design.md) | Siguiente: [delta](delta.md)

Este archivo se escribe por entregas y no se reescribe: la sección de cada entrega se añade a las anteriores.

## Entrega a · boceto, lista y alta (F1 a F6)

### Qué se implementó

La entrega a deja el catálogo de proveedores en modo lectura y con el alta operativa para Compras. La sección «Proveedores» deja de ser un marcador: `/compras/proveedores` pinta una tabla con nombre, RFC, estado, día de corte y día de pago, con filtro por estado, búsqueda por nombre o RFC y paginación de 50 en 50. Solo el rol `COMPRAS` ve el botón `+` y las acciones por fila, que salen del estado que devolvió el servidor: `ACTIVO` ofrece Editar, Desactivar y Dar de baja; `DESACTIVADO`, Editar y Dar de baja; `BAJA`, ninguna. El botón `+` abre el alta con el formulario compartido de TKT-008c: valores por omisión jueves y sábado (`RN-17`), tope de consignación como cadena, `422` junto a su campo y el conflicto `RFC_DUPLICADO` en línea, con el proveedor existente y sin acción de verlo (H-1).

Las acciones por fila de la lista (Editar, Desactivar, Dar de baja) están pintadas y todavía no hacen nada: las conectan las filas F7 y F8 de la entrega b. Antes de escribir código, F1 dejó en `docs/08-wireframes.md` el boceto «2c · Pantalla Proveedores» y reconcilió la viñeta del proveedor de la pantalla 8 con las dos operaciones distintas, desactivar y dar de baja.

### Ajustes respecto al design

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-11-17 | F3 eliminada: no se añade `soloLectura` a `FormularioCatalogo` ni se escribe TC-F04. | TKT-012b (PR #80, ya fusionado) introdujo `soloLectura` con el mismo nombre. Su semántica añade que el campo de solo lectura no viaja en `alGuardar`; no estorba, porque el `PATCH` de la entrega b envía solo lo cambiado. Registrado en «Ajustes de la ejecución» de `design.md`. |
| 2026-11-17 | Las mutaciones de `proveedores.consultas.ts` no invalidan la caché por sí mismas; lo hace la pantalla. | Es el patrón de obras (`(api, ...)` sin `QueryClient`). El diseño decía «tras cada mutación exitosa se invalida»: el efecto es el mismo y queda probado en TC-F19. |
| 2026-11-17 | El tope de consignación se rotula «Tope de consignación (opcional)». | El boceto lo dibuja con «opcional» al final. Las pruebas lo buscan con `/^Tope de consignación/`. |
| 2026-11-17 | Un `alBloqueo` del alta cierra el formulario y pinta un aviso de cabecera con el mensaje y la referencia. | `POST /proveedores` y `PATCH /proveedores/{proveedor_id}` pueden responder `409` `CONCURRENCIA` (`BLOQUEO_VENCIDO`) si vence el bloqueo; el alta y la edición cierran el formulario y avisan en la cabecera con el mensaje del servidor y su referencia, y lo capturado se pierde. La persona dueña decidió el 2026-11-18 dejarlo así: no se ofrece «Reintentar». |
| 2026-11-17 | El RFC en minúsculas se normaliza a mayúsculas y se acepta. | El servidor hace la misma normalización; la tabla de entradas hostiles del diseño decía «minúsculas» entre lo rechazable y el texto del esquema decía «recortado y en mayúsculas». Se siguió el texto del esquema. |
| 2026-11-18 | Por el hallazgo F001 de `auditor-docs`, el boceto y la viñeta de la pantalla 8 marcan la baja terminal como supuesto `(asumido, PA-24)`, y se añadió su fila a §13 de `docs/08-wireframes.md`. | La baja definitiva que conserva el RFC no figuraba como supuesto en el wireframe ni en el diseño, y la auditoría de documentación lo pidió. |

### Archivos tocados

| Archivo | Acción | Capa |
|---|---|---|
| `docs/08-wireframes.md` | modificado: subsección 2c, viñeta *Proveedor* de la pantalla 8 y texto del `403` en la pantalla 6 | documentación |
| `frontend/src/compartido/componentes/bloqueo/etiquetas.ts` | modificado: tabla `ordenes`, rótulos `proveedor_existente` y `estado_actual`, clave oculta `proveedor_existente_id`, etiqueta `DESACTIVAR_PROVEEDOR` | frontend |
| `frontend/src/modulos/proveedores/catalogo/proveedores.consultas.ts` | nuevo | frontend |
| `frontend/src/modulos/proveedores/catalogo/proveedores.formulario.ts` | nuevo | frontend |
| `frontend/src/modulos/proveedores/catalogo/estados-lista.tsx` | nuevo | frontend |
| `frontend/src/modulos/proveedores/catalogo/PantallaProveedores.tsx` | nuevo | frontend |
| `frontend/src/modulos/proveedores/rutas.tsx` | modificado: la pantalla sustituye al marcador, misma ruta y misma guarda | frontend |
| `frontend/src/pruebas/cuerpos.ts` | modificado: fábrica `proveedor` | pruebas |
| `frontend/src/compartido/componentes/bloqueo/PantallaBloqueo.test.tsx` | modificado: pruebas nuevas TC-F02 y TC-F03 | pruebas |
| `frontend/src/compartido/formularios/ConflictoEnLinea.test.tsx` | modificado: prueba nueva TC-F01 | pruebas |
| `frontend/src/compartido/formularios/FormularioCatalogo.test.tsx` | modificado: **cuatro líneas, D-10** | pruebas |
| `frontend/src/modulos/proveedores/catalogo/proveedores.formulario.test.ts` | nuevo | pruebas |
| `frontend/src/modulos/proveedores/catalogo/proveedores.consultas.test.ts` | nuevo | pruebas |
| `frontend/src/modulos/proveedores/catalogo/PantallaProveedores.test.tsx` | nuevo | pruebas |
| `frontend/src/modulos/proveedores/catalogo/PantallaProveedores.ruta.test.tsx` | nuevo | pruebas |
| `frontend/src/modulos/proveedores/catalogo/PantallaProveedores.alta.test.tsx` | nuevo | pruebas |
| `sdd/tickets/tkt-032a/rojo/fila-2.txt`, `fila-4.txt`, `fila-5.txt`, `fila-6.txt` | nuevo: salida literal de cada rojo, con la ruta local sustituida por `<scratchpad>` tras el hallazgo F001 de seguridad | evidencia |
| `sdd/tickets/tkt-032a/rojo/correccion-1.txt` | nuevo: salida del rojo de las pruebas añadidas en el ciclo de corrección 1 | evidencia |
| `frontend/src/modulos/proveedores/catalogo/proveedores.consultas.ts` y `PantallaProveedores.tsx` | modificados en el ciclo 1: `TAMANO_PAGINA` y `totalDePaginas` exportados desde la consulta, página vacía que ya es la última sin esqueleto infinito, comentario de F7 y F8 | frontend |
| `docs/08-wireframes.md`, `sdd/tickets/tkt-032a/design.md` y `spec.md` | modificados en el ciclo 1: la baja terminal se marca `(asumido, PA-24)` y se añade la fila 2c a §13; el *Must* de la spec dice «sin acción de verlo» | documentación |

**Cambio declarado a una prueba existente (D-10).** En `FormularioCatalogo.test.tsx`, el test `tkt008_ca11_esc07 · la baja la rechaza el servidor` busca el botón por la clave cruda `DESACTIVAR_PROVEEDOR` en cuatro líneas (443, 445, 447 y 456) y pasa a buscar «Desactivar el proveedor», porque `etiquetas.ts` ya rotula esa acción. `VER_ORDENES_ABIERTAS` sigue cruda. Es el único cambio a una prueba existente y lo aprobó la persona dueña el 2026-11-17.

### Pruebas

| # | Test | Tipo | Criterio | Antes del código | Al cerrar |
|---|---|---|---|---|---|
| TC-F01 | `hdu004_esc03` · el conflicto pinta «Proveedor existente», no el UUID ni la clave cruda | feliz | `CA-3` | FALLA | PASA |
| TC-F02 | `hdu004_esc12` · tabla «Órdenes pendientes» y «Estado actual», no JSON ni clave cruda | feliz | `CA-8` (etiquetas) | FALLA | PASA |
| TC-F03 | `hdu004_esc12` · «Desactivar el proveedor» se rotula; sin acciones solo queda «Cerrar» | **rechazo** | `CA-8` (etiquetas) | FALLA el rótulo; la guarda de «sin acciones» nace en verde | PASA |
| TC-F05, TC-F06, TC-F08 | `proveedores.formulario.test.ts`: esquema de alta y edición, `cambiosDe`, tope idéntico y como cadena | feliz · **rechazo** | `CA-4`, `CA-R4` | FALLA (112) | PASA |
| TC-F07 y mutaciones | `proveedores.consultas.test.ts`: `estado=ACTIVO` siempre, `q` solo si no está vacía, cuatro mutaciones con su contrato de error | feliz · **rechazo** | `CA-1`, `CA-R4` | FALLA (43) | PASA |
| TC-F09 a TC-F14 | `PantallaProveedores.test.tsx`: lista, cuatro estados, filtro, búsqueda, paginación, rótulos de estado | feliz · borde · **rechazo** | `CA-1` | FALLA | PASA |
| TC-F15 | acciones exactas por estado para Compras | feliz | `CA-6`, `CA-7`, `CA-9` | FALLA | PASA |
| TC-F16 | los otros cinco roles ven la lista y ninguna acción ni el `+` | **rechazo** | `CA-9` | FALLA | PASA |
| TC-F17 | guarda, menú, título y redirección sin sesión de `/compras/proveedores` (9 pruebas) | **regresión** | `CA-R1` | PASA (nace en verde: el marcador ya cumplía) | PASA |
| TC-F18 a TC-F22 y `403` | `PantallaProveedores.alta.test.tsx` (21): `+` con foco, alta con valores por omisión y con tope, `RFC_DUPLICADO` en línea sin botón, `422` por cada campo, `403` con el mensaje del servidor | feliz · **rechazo** | `CA-2`, `CA-3`, `CA-4`, `CA-9`, `CA-R4` | FALLA (21) | PASA |

### Ciclo TDD por fila

| Fila | Rojo (salida o ruta) | Ejecutó | Verde | Tabla «mutante · test que cae» |
|---|---|---|---|---|
| F1 | No aplica (documentación) | `desarrollador-react` no se despachó: el orquestador pegó el texto del diseño | `verificar_docs.py` sin problemas propios de la fila y `markdownlint-cli2` con 0 errores | No aplica |
| F2 | `rojo/fila-2.txt`: 5 failed, 80 passed, 0 errores | `tester-frontend` · `desarrollador-react` | 85 passed (5 archivos) | No aplica |
| F3 | — | eliminada | — | — |
| F4 | `rojo/fila-4.txt`: 155 failed, 0 errores (rojo con módulos de producción stub que lanzaban «pendiente») | `tester-frontend` · `desarrollador-react` | 155 passed; suite completa 785 passed | No aplica |
| F5 | `rojo/fila-5.txt`: 44 failed, 9 passed (regresión), 0 errores | `tester-frontend` · `desarrollador-react` | 53 passed; suite completa 838 passed | Sí, abajo |
| F6 | `rojo/fila-6.txt`: 21 failed, 0 errores | `tester-frontend` · `desarrollador-react` | 21 passed; suite completa 859 passed (36 archivos) | Sí, abajo |

**Resumen de la salida del verde de cierre de la entrega** (corrida del 2026-11-17, con Docker respondiendo, sobre la copia sincronizada del repositorio):

```text
 Test Files  36 passed (36)
      Tests  859 passed (859)
```

**Refactor.** Sin refactor en F2, F4, F5 y F6: el código nació en el mínimo que pone las pruebas en verde y copia el patrón de obras.

**Tests devueltos al tester.** Ninguno.

**Mutación en rutas críticas.** Corrida por el orquestador sobre una copia en el scratchpad, con el repositorio intacto: `git status` y las huellas SHA-256 de `PantallaProveedores.tsx`, `proveedores.consultas.ts` y `proveedores.formulario.ts` fueron idénticas antes y después de cada mutante, y la copia se restauró desde el repositorio tras cada uno.

| Mutante | Cambio | Test que cae |
|---|---|---|
| `M-1` | «Desactivar» también se ofrece a `DESACTIVADO` | `hdu004_esc12 · TC-F15 · una fila DESACTIVADO de Compras ofrece exactamente sus acciones` |
| `M-2` | acciones de Editar y Dar de baja a `BAJA` | `hdu004_esc12 · TC-F15 · una fila BAJA de Compras ofrece exactamente sus acciones` |
| `M-3` | `puedeOperar` verdadero para todo rol | 10 pruebas: `TC-F16` de los cinco roles y `TC-F10` «vacío» de los cinco roles |
| `M-4` | el tope pasa por `Number` antes del `POST` | `TC-F08` (tope máximo) y las dos de `TC-F20` |
| `M-5` | el filtro «Activos» deja de enviar `estado=ACTIVO` | `TC-F11` (por omisión), `TC-F12` (búsqueda) y `TC-F12` (buscar desde la página 2) |

**Nota sobre M-5.** Mutar el valor por omisión de `proveedores.consultas.ts` no pone nada en rojo en las pruebas de pantalla, porque la pantalla siempre pasa `estados` de forma explícita; es un mutante equivalente a nivel de pantalla y las pruebas de `proveedores.consultas.test.ts` cubren ese valor por omisión. El mutante válido es el de la pantalla.

### Entorno de ejecución

`frontend/node_modules` quedó incompleto: un `npm ci` lanzado por un agente falló con `EPERM` porque un servidor de desarrollo de la persona dueña (`npm run dev`) tenía tomado un binario nativo, y nadie lo detuvo. Para no tocar el proceso, las pruebas, el lint y el typecheck se corrieron sobre una copia sincronizada de `frontend/` en el scratchpad, que se rehace con `robocopy` antes de cada corrida. El resultado es el mismo que en el repositorio porque `src` es idéntico. **Quien retome el trabajo debe parar ese servidor y volver a ejecutar `npm ci` en `frontend/`.** No se ejecutó `npm run tipos:verificar` porque no cambia el contrato y exige `uv`; lo corre la entrega b (F9).

## Modelo por paso

| Paso | Agente | Modelo previsto | Modelo usado | Motivo del cambio |
|---|---|---|---|---|
| Apertura de rama | `git-entrega` | `haiku` | `haiku` | — |
| F2 · rojo | `tester-frontend` | `sonnet` | `sonnet` | — |
| F2 · verde | `desarrollador-react` | `haiku` | `haiku` | — |
| F4 · rojo | `tester-frontend` | `sonnet` | `sonnet` | — |
| F4 · verde | `desarrollador-react` | `haiku` | `haiku` | — |
| F5 · rojo | `tester-frontend` | `sonnet` | `sonnet` | — |
| F5 · verde | `desarrollador-react` | `sonnet` | `sonnet` | Disparador «los permisos de un rol» (§14.2), como fija el diseño |
| F6 · rojo | `tester-frontend` | `sonnet` | `sonnet` | — |
| F6 · verde | `desarrollador-react` | `haiku` | `haiku` | — |
| Auditoría de cierre | `auditor-arquitectura` | `sonnet` | `sonnet` | — |

## Resultado contra los criterios de aceptación (entrega a)

| Criterio | Nivel | Estado | Evidencia |
|---|---|---|---|
| `CA-1` | `[M]` | Cumplido | TC-F07, TC-F09 a TC-F14 |
| `CA-2` | `[M]` | Cumplido | TC-F18 a TC-F20 |
| `CA-3` | `[M]` | Cumplido, con la lectura de H-1 (muestra al existente, sin acción de verlo) | TC-F01, TC-F21 |
| `CA-4` | `[M]` | Cumplido | TC-F05, TC-F22 |
| `CA-9` | `[M]` | Parcial: la entrega a cubre la ocultación por rol, el `403` del alta y la redirección sin sesión. El `403` de las operaciones de estado es TC-F36 (entrega b) | TC-F15, TC-F16, TC-F17, prueba del `403` del alta |
| `CA-R1` | `[M]` | Cumplido | TC-F17 |
| `CA-R4` | `[M]` | Parcial: la parte del alta; el resto es la entrega b | TC-F05, TC-F08, TC-F20, `M-4` |
| `CA-5` a `CA-8`, `CA-10`, `CA-11`, `CA-R2`, `CA-R3` | `[M]` | Pendientes de la entrega b | — |

`CA-R2` se comprobó de forma parcial: las 85 pruebas de TKT-008c y de bloqueo pasan con el único cambio declarado de D-10.

## Auditorías

| Auditor | Veredicto | Hallazgos | Ciclos |
|---|---|---|---|
| `auditor-arquitectura` | `APROBADO` (en `/sdd-ejecutar` y de nuevo en `/sdd-revisar`) | 0 críticos, 0 mayores, 0 menores y 3 observaciones sin acción | 1 |
| `auditor-sql` | No aplica | La entrega no tiene esquema ni migración | — |
| `auditor-codigo` | `APROBADO` tras el ciclo 1 | Primera pasada: 1 Mayor y 4 Menores; los cinco quedaron `Resuelto` | 2 |
| `auditor-seguridad` | `APROBADO` | 2 observaciones Baja: la F001 se corrigió en el ciclo 1; la F002 (`maxLength`) no se aplica, porque el control real es el servidor | 1 |
| `auditor-docs` | `APROBADO` tras el ciclo 1 | Primera pasada: 1 Mayor y 3 Menores; los cuatro quedaron `Resuelto` | 2 |

### Hallazgos y su resolución

| ID | Auditor | Severidad | Ubicación | Hallazgo | Estado |
|---|---|---|---|---|---|
| O-1 | `auditor-arquitectura` | Observación | `PantallaProveedores.tsx`, `alAccion` del alta | `alAccion` es una función vacía: hoy `RFC_DUPLICADO` llega sin acciones (H-1). Si un ticket de backend añade `VER_PROVEEDOR`, habrá que revisarlo. | Aceptado: es la decisión H-1 |
| O-2 | `auditor-arquitectura` | Observación | `PantallaProveedores.tsx`, botones de fila | Los botones Editar, Desactivar y Dar de baja se pintan sin acción hasta la entrega b. No fusionar la entrega a sola. | Aceptado: un solo PR por ticket, se abre al aprobarse la entrega b |
| O-3 | `auditor-arquitectura` | Observación | `PantallaProveedores.tsx` y `proveedores.consultas.ts` | `TAMANO_PAGINA = 50` está duplicado en dos archivos. | Se resuelve en la entrega b si toca esos archivos; si no, queda anotado |
| C-F001 | `auditor-codigo` | Mayor | `PantallaProveedores.tsx` y `proveedores.consultas.ts` | `TAMANO_PAGINA` duplicado y cálculo de páginas repetido (incluye la O-3 de arquitectura) | Resuelto: constante y `totalDePaginas` en la consulta |
| C-F002 | `auditor-codigo` | Menor | `PantallaProveedores.tsx` | Esqueleto infinito con página vacía, `total` mayor que cero y última página igual a la actual | Resuelto, con prueba nueva en rojo antes del código |
| C-F003 | `auditor-codigo` | Menor | `PantallaProveedores.tsx` | Rama `alBloqueoAlta` sin prueba | Resuelto con prueba nueva; el mutante ahora cae |
| C-F004 | `auditor-codigo` | Menor | `proveedores.consultas.ts` | `.trim()` de `q` sin prueba | Resuelto con prueba nueva; el mutante ahora cae |
| C-F005 | `auditor-codigo` | Menor | `PantallaProveedores.tsx` | Comentario que citaba filas de trabajo | Resuelto |
| S-F001 | `auditor-seguridad` | Baja | `rojo/fila-*.txt` | Ruta local con el nombre de usuario en la evidencia | Resuelto: prefijo sustituido por `<scratchpad>` |
| S-F002 | `auditor-seguridad` | Baja | `PantallaProveedores.tsx` | Búsqueda sin `maxLength` de 200 | Aceptado: cortesía opcional, el servidor responde `422` |
| D-F001 | `auditor-docs` | Mayor | `docs/08-wireframes.md` | La baja terminal sin `(asumido, PA-24)` | Resuelto, con la fila 2c de §13 |
| D-F002 a D-F004 | `auditor-docs` | Menor | `spec.md` e `impl.md` | *Must* de la spec contradecía H-1; cifra de CRLF y fecha de la corrida sin copiar de la salida | Resuelto |

### Qué verificó el auditor (copiado de su informe)

- **Dinero nunca flotante.** `grep` por `Number(`, `parseInt`, `parseFloat`, `toFixed` e import directo de `decimal.js` en `modulos/proveedores`: sin coincidencias. El tope entra y sale como cadena y `cambiosDe` compara con `Decimal.eq` vía `@/compartido/dinero/dinero`. Un mutante propio (tope por `parseFloat`) hizo caer 13 pruebas.
- **El cliente nunca decide una regla.** Las acciones por fila salen del `estado` que devolvió el servidor; ninguna acción de bloqueo está cableada; `etiquetas.ts` solo añade rótulos. Dos mutantes propios cayeron (`BAJA` con acción y `puedeOperar` verdadero).
- **Fronteras de módulo.** El módulo del cliente solo importa de `@/api`, `@/components/ui`, `@/compartido` y de la guarda y la tabla de secciones de `@/app`; ningún otro módulo de `modulos/`.
- **Fase 2 y backend.** Sin captura sin conexión, evidencia, nómina ni destajo. Sin cambios a `cimenta/`, `migraciones/` ni `docs/api/openapi.yaml`.
- **Obras y pruebas de TKT-008c.** `PantallaObras.tsx` no figura en el diff. `FormularioCatalogo.test.tsx` cambia exactamente las cuatro líneas de D-10; `PantallaBloqueo.test.tsx` y `ConflictoEnLinea.test.tsx` solo suman líneas.
- **Secretos, contrato de error y camino no feliz.** Sin secretos; ningún `RN-xx` inventado; rechazos para cada `422`, `RFC_DUPLICADO`, `403`, rol sin sección, sin sesión, y errores de la lista.
- **Máquina (primera pasada, antes del ciclo 1).** Lint y typecheck limpios; 36 archivos y 859 pruebas en verde; `verificar_docs.py` sin problemas y `markdownlint-cli2` con 0 problemas.

## Hallazgos fuera de alcance

| Archivo | Observación | Prioridad |
|---|---|---|
| `frontend/src/modulos/proveedores/catalogo/estados-lista.tsx` | Copia local de `EsqueletoLista` y `AvisoErrorLista` de obras. Ticket de refactor sugerido: extraerlos a `compartido/componentes/lista/` y usarlos en ambas pantallas. | Baja |
| `frontend/src/modulos/proveedores/catalogo/proveedores.*.test.ts` | La fábrica `proveedor` está duplicada de forma local en los dos archivos de F4 y también en `pruebas/cuerpos.ts`. Unificarla con un cambio de pruebas posterior. | Baja |
| `frontend/node_modules` | Incompleto por el `npm ci` fallido; ver «Entorno de ejecución». | Media: acción de la persona dueña |

## Documentación actualizada

| Documento | Qué cambió |
|---|---|
| `docs/08-wireframes.md` | Subsección «2c · Pantalla Proveedores»; viñeta *Proveedor* de la pantalla 8 reconciliada con las dos operaciones; el `403` de la pantalla 6 pasa a ser el mensaje del servidor, sin cifras (D-6). |
| `sdd/tickets/tkt-032a/design.md` | Fila F3 marcada «Ajustado · eliminada» y tabla de «Ajustes de la ejecución». |

`python tools/verificar_docs.py` → sin problemas una vez existe este archivo; queda el aviso informativo de que 16 archivos tienen CRLF en la copia de trabajo y LF en el índice (salida de `verificar_docs.py` del 2026-11-18).

## Verificación de la entrega

- [x] Criterios `[M]` de la entrega a cumplidos con evidencia (los parciales están señalados)
- [x] Ciclo TDD por fila: rojo antes de verde, ningún test editado por un desarrollador (el único cambio a una prueba existente es D-10, hecho por el tester)
- [x] Suite del cliente en verde: 863 pruebas tras el ciclo de corrección 1
- [x] Al menos un test de rechazo por regla implicada
- [x] Mutación en rutas de permiso y de estado, con huellas y `git status` idénticos
- [x] Auditoría de arquitectura `APROBADO`
- [x] Documentación afectada actualizada en el mismo cambio
- [x] Lint y typecheck limpios
- [x] Sin secretos en el diff; rama `tkt-032a-pantalla-proveedores`

## Verificación final · entrega a

Corrida del 2026-11-18 por el orquestador, con Docker respondiendo (`docker info` da 29.9.3), sobre la copia sincronizada de `frontend/` y la raíz del repositorio:

```text
 Test Files  36 passed (36)
      Tests  863 passed (863)
```

`npm run lint` (`eslint .`) y `npm run typecheck` (`tsc --noEmit`) terminan sin salida de error. `python tools/verificar_docs.py` termina con «✓ Sin problemas» y el aviso informativo de CRLF de 16 archivos.

| Criterio | Nivel | Resultado en la entrega a |
|---|---|---|
| `CA-1`, `CA-2`, `CA-3`, `CA-4`, `CA-R1` | `[M]` | Cumplido, con la evidencia de «Resultado contra los criterios de aceptación» |
| `CA-9`, `CA-R4` | `[M]` | Parcial en la entrega a, como se declaró; se completan en la entrega b |
| `CA-5` a `CA-8`, `CA-10`, `CA-11`, `CA-R2`, `CA-R3` | `[M]` | Pendientes de la entrega b |

**Auditorías.** `auditor-arquitectura` y `auditor-seguridad`: `APROBADO`. `auditor-codigo` y `auditor-docs`: `REQUIERE CAMBIOS` en la primera pasada y `APROBADO` tras un ciclo de corrección, con todos los hallazgos `Resuelto` y ninguno `Nuevo`.

**Desviaciones.** F3 eliminada (TKT-012b ya trajo `soloLectura`); la baja terminal se marca como supuesto `(asumido, PA-24)`. Ninguna cambia el alcance.

**Qué queda pendiente.** La entrega b (F7 a F10) y arreglar `frontend/node_modules`. La entrega a no se fusiona ni se despliega sola: los botones de fila no hacen nada hasta F7 y F8.

## Entrega b · edición, estado y extremo a extremo (F7 a F10)

### Qué se implementó

La entrega b conecta las acciones de fila que la entrega a solo pintaba. «Editar» abre el formulario compartido con el RFC visible y de solo lectura, y el `PATCH` envía únicamente lo que cambió (el tope solo como cadena, y `null` si se vacía); guardar sin cambios cierra sin enviar nada. «Desactivar» y «Dar de baja» piden un motivo y usan la fila pulsada como objetivo. Un `409` de la baja con órdenes pendientes se pinta con la pantalla de bloqueo sobre la tabla: la acción «Desactivar el proveedor» aparece solo si el servidor la manda en `acciones[]` y abre el motivo de desactivar del mismo proveedor que se intentó dar de baja. El estado ya no válido, la espera de concurrencia y los avisos de `403`, `404`, `500` y red tienen cada uno su camino. Una prueba de contrato ata las cinco llamadas a `servidor.ts`, y un recorrido de extremo a extremo con una orden `PARCIAL` real prueba el `409` de la baja contra el servidor.

### Ajustes respecto al design

Los tres ajustes de la entrega (la prueba corregida de F7, la extracción de `TablaProveedores.tsx` y el prefijo `EEE` del RFC de prueba, con la línea `FOLIO=` del sembrador) están en «Ajustes de la ejecución» de `design.md`, con fecha 2026-11-18. Ninguno cambia el alcance.

### Archivos tocados

| Archivo | Acción | Capa |
|---|---|---|
| `frontend/src/modulos/proveedores/catalogo/PantallaProveedores.tsx` | modificado: edición, captura de motivo, bloqueo y avisos | frontend |
| `frontend/src/modulos/proveedores/catalogo/proveedores.formulario.ts` | modificado: `camposEdicion` y `esquemaVistaEdicionProveedor` | frontend |
| `frontend/src/modulos/proveedores/catalogo/TablaProveedores.tsx` | nuevo: tabla y acciones por estado, extraídas en el refactor de F8 | frontend |
| `frontend/src/modulos/proveedores/catalogo/PantallaProveedores.edicion.test.tsx` | nuevo (27 pruebas) | pruebas |
| `frontend/src/modulos/proveedores/catalogo/PantallaProveedores.estado.test.tsx` | nuevo (29 pruebas) | pruebas |
| `frontend/src/modulos/proveedores/catalogo/proveedores.contrato.test.ts` | nuevo (6 pruebas) | pruebas |
| `frontend/e2e/proveedores.spec.ts` y `frontend/e2e/sembrar-orden.ts` | nuevos: dos recorridos y la ayuda que invoca al sembrador | pruebas |
| `backend/herramientas/semilla_orden_proveedor_local.py` | nuevo: sembrador local de una orden `PARCIAL` (apoyo de pruebas, H-2) | herramientas |
| `backend/herramientas/soporte_tkt029b_ordenes.py` | modificado: solo el docstring | herramientas |
| `docs/arranque-local.md` | modificado: un párrafo con el sembrador | documentación |
| `sdd/tickets/tkt-032a/rojo/fila-7.txt`, `fila-8.txt`, `fila-9.txt`, `fila-10.txt` y `fila-10-verde.txt` | nuevos: salida literal de cada rojo y del verde del E2E | evidencia |

Ningún archivo de `backend/cimenta/`, de las migraciones ni de `docs/api/openapi.yaml` cambió, y `PantallaObras.tsx` y los componentes compartidos tampoco.

### Pruebas

| # | Test | Tipo | Criterio | Antes del código | Al cerrar |
|---|---|---|---|---|---|
| TC-F23 a TC-F26 y D-7 | `PantallaProveedores.edicion.test.tsx` (27): RFC de solo lectura, `PATCH` solo con lo cambiado, sin cambios no hay petición, `422`, `404` con recarga y `403` | feliz · borde · **rechazo** | `CA-5` | FALLA (26; 1 guarda de `BAJA` nace en verde) | PASA |
| TC-F27 a TC-F30 | desactivar y dar de baja con motivo, y sin motivo | feliz · **rechazo** | `CA-6`, `CA-7` | FALLA | PASA |
| TC-F31 a TC-F34 | bloqueo con órdenes pendientes: acción tomada de `acciones[]`, mismo proveedor, sin acción con `DESACTIVADO` o con `acciones: []` | **rechazo** | `CA-8` | FALLA | PASA |
| TC-F35 | `ESTADO_NO_PERMITE_OPERACION` con «Estado actual» rotulado y lista recargada | **rechazo** | `CA-10` | FALLA | PASA |
| TC-F36 | `403` sin cifras, `404` con recarga, `500`, red y `CONCURRENCIA` con «Reintentar» | **rechazo** | `CA-9`, `CA-10` | FALLA (29 en total con las de F31 a F35) | PASA |
| TC-F37 | `proveedores.contrato.test.ts` (6): cada ruta, método y cuerpo existe en `servidor.ts` | contrato | `CA-R3` | NACE EN VERDE: las funciones existen desde F4; el valor está en los mutantes | PASA |
| TC-E1 | `hdu004_esc02 · recorrido del catálogo` | feliz · **rechazo** (RFC repetido) | `CA-11`, `CA-2`, `CA-3`, `CA-6` | PASA (usa solo la pantalla ya construida) | PASA |
| TC-E2 | `hdu004_esc12 · baja bloqueada por una orden PARCIAL real` | **rechazo** | `CA-8`, `CA-11` | FALLA: falta el sembrador | PASA |

### Ciclo TDD por fila

| Fila | Rojo (salida o ruta) | Ejecutó | Verde | Tabla «mutante · test que cae» |
|---|---|---|---|---|
| F7 | `rojo/fila-7.txt`: 26 failed, 1 passed (guarda de `BAJA`), 0 errores | `tester-frontend` · `desarrollador-react` | 103 passed en `PantallaProveedores` | No aplica |
| F8 | `rojo/fila-8.txt`: 29 failed, 0 errores | `tester-frontend` · `desarrollador-react` | 208 passed en las cuatro suites del diseño; 919 passed en la suite completa | Sí, abajo |
| F9 | `rojo/fila-9.txt`: nace en verde (6 passed) con cinco mutantes de ruta, método y cuerpo que la ponen en rojo | `tester-frontend` | 6 passed; `tipos:verificar` «Tipos al día» | Sí, en `rojo/fila-9.txt` |
| F10 | `rojo/fila-10.txt`: 9 passed y 1 failed (TC-E2: «No module named herramientas.semilla_orden_proveedor_local») | `tester-frontend` · `desarrollador-aplicacion` | `rojo/fila-10-verde.txt`: 10 passed | No aplica |

**Evidencia de cierre de la entrega** (corrida del 2026-11-18, con Docker respondiendo, `docker info` da 29.9.3):

```text
Cliente (vitest, copia sincronizada):  Test Files  39 passed (39)  ·  Tests  925 passed (925)   [al cerrar la ejecución; 931 tras el ciclo de corrección de la revisión]
Extremo a extremo (playwright):        10 passed (24.1s)
```

`npm run lint`, `npm run typecheck` y `npm run tipos:verificar` («Tipos al día») terminan limpios. Desde `backend/`, `lint-imports` da «Contracts: 16 kept, 0 broken», `ruff check .` «All checks passed!», `mypy .` «no issues found in 376 source files» y `verificar_float` «archivos revisados: 42; hallazgos: 0». `uv run pytest tests/test_tkt029b_ordenes_pendientes.py tests/test_tkt029b_api_baja.py` da 49 passed. Las 925 pruebas del cliente al cerrar la ejecución suman las 863 de la entrega a y las 62 nuevas (27 + 29 + 6); el ciclo de corrección de la revisión añadió 6 más, hasta 931.

**Refactor.** En F8, `TablaProveedores.tsx` se extrajo de la pantalla con la suite en verde. F7, F9 y F10: sin refactor.

**Tests devueltos al tester.** En F7, el caso `ACTIVO` del bloque D-7 elegía «viernes», el día de pago que ya tenía el proveedor de la prueba, así que `cambiosDe` no enviaba nada. El desarrollador lo devolvió sin editarlo y el tester lo cambió a «lunes» con `{ dia_pago: 1 }`.

**Mutación en rutas críticas.** Corrida por el orquestador sobre una copia en el scratchpad, con el repositorio intacto: `git status` y las huellas SHA-256 de `PantallaProveedores.tsx` y `TablaProveedores.tsx` fueron idénticas antes y después, y la copia se restauró tras cada mutante.

| Mutante | Cambio | Test que cae |
|---|---|---|
| `M-6` | el bloqueo siempre lleva la acción `DESACTIVAR_PROVEEDOR`, venga o no en `acciones[]` | 6 pruebas: TC-F33, TC-F34, las dos de TC-F35 y las dos de `CONCURRENCIA` de TC-F36 |
| `M-7` | la acción del bloqueo desactiva a la primera fila de la lista en lugar del proveedor bloqueado | las dos de TC-F32 |

Los mutantes `M-1` a `M-5` de la entrega a siguen valiendo contra la suite acumulada, que contiene sus pruebas sin cambio.

### Entorno de ejecución

`frontend/node_modules` sigue incompleto, así que el cliente se probó sobre la copia sincronizada. Para el extremo a extremo se montó en el scratchpad una disposición que imita la raíz del repositorio (copia de `frontend/`, `docs/api/openapi.yaml` y un enlace a `backend/`), y se copió el archivo `.env` local al scratchpad **sin leerlo** para que Playwright arrancara el backend; la copia se borró al terminar. El extremo a extremo siembra datos en la base local acumulativa (proveedores `E2E-…`, una orden `OC-E2E-…`).

## Modelo por paso (entrega b)

| Paso | Agente | Modelo previsto | Modelo usado | Motivo del cambio |
|---|---|---|---|---|
| F7 · rojo | `tester-frontend` | `sonnet` | `sonnet` | — |
| F7 · verde | `desarrollador-react` | `haiku` | `haiku` | — |
| F7 · prueba devuelta | `tester-frontend` | `sonnet` | `sonnet` | — |
| F8 · rojo | `tester-frontend` | `sonnet` | `sonnet` | — |
| F8 · verde | `desarrollador-react` | `sonnet` | `sonnet` | Disparador «los permisos de un rol» (§14.2), como fija el diseño |
| F9 · rojo | `tester-frontend` | `sonnet` | `sonnet` | — |
| F10 · rojo | `tester-frontend` | `sonnet` | `sonnet` | — |
| F10 · verde | `desarrollador-aplicacion` | `haiku` | `haiku` | — |
| Auditoría de cierre | `auditor-arquitectura` | `sonnet` | `sonnet` | — |

## Resultado contra los criterios de aceptación (entrega b)

| Criterio | Nivel | Estado | Evidencia |
|---|---|---|---|
| `CA-5` | `[M]` | Cumplido | TC-F23 a TC-F26 |
| `CA-6` | `[M]` | Cumplido | TC-F27, TC-F28, TC-E1 |
| `CA-7` | `[M]` | Cumplido | TC-F29, TC-F30 |
| `CA-8` | `[M]` | Cumplido | TC-F31 a TC-F34, TC-E2 |
| `CA-9` | `[M]` | Cumplido | TC-F15, TC-F16, TC-F17 (entrega a) y el `403` del alta, la edición y las operaciones de estado (TC-F36) |
| `CA-10` | `[M]` | Cumplido | TC-F35, TC-F36 |
| `CA-11` | `[M]` | Cumplido | TC-E1, TC-E2 (10 passed en el E2E) |
| `CA-R2` | `[M]` | Cumplido con el cambio declarado D-10 | las suites de `FormularioCatalogo`, `CapturaMotivo`, `ConflictoEnLinea` y `PantallaBloqueo` en verde |
| `CA-R3` | `[M]` | Cumplido | TC-F37 y `tipos:verificar` |
| `CA-R4` | `[M]` | Cumplido | TC-F08, TC-F20, TC-F24 y `M-4` |

## Auditorías (entrega b)

| Auditor | Veredicto | Hallazgos | Ciclos |
|---|---|---|---|
| `auditor-arquitectura` | `APROBADO` | 0 críticos, 0 mayores, 0 menores y 2 observaciones sin acción | 1 |
| `auditor-sql` | No aplica | Sin esquema ni migración; el sembrador solo inserta con SQL parametrizado | — |

Observaciones: **O-1** el sembrador importa `normalizar_rfc` del dominio de `proveedores` y consulta tablas por SQL, como ya hacen los demás sembradores de `herramientas/` (que `import-linter` no analiza); si otro código lo necesita, conviene publicarlo en `proveedores.interfaz`. **O-2** la orden `PARCIAL` lleva una cantidad recibida sin movimientos de inventario y su requisición entra al consumido de la obra de humo; solo afecta a la base local y el E2E no afirma cifras de semáforo.

### Qué verificó el auditor (copiado de su informe)

- **El cliente nunca decide una regla.** El bloqueo lo pinta `PantallaBloqueo` desde `error.acciones`; el objetivo es el proveedor guardado al rechazarse la operación, no `accion.ruta` ni la primera fila; las acciones por fila salen de `proveedor.estado`. TC-F32, TC-F33 y TC-F34 y los mutantes `M-6` y `M-7` lo cubren.
- **Dinero nunca flotante.** `topeCambio` compara con `Decimal.eq`; sin `Number`, `parseFloat` ni `parseInt` en el módulo, el sembrador, el spec y la ayuda; `verificar_float` limpio.
- **El sembrador.** `exigir_base_local()` antes de leer variables y de crear el motor, SQL parametrizado, `commit()` y `rollback()`, rol de aplicación, solo `INSERT` en `requisicion`, `orden_compra` y `orden_compra_renglon`; sin cambios en `cimenta/`, migraciones ni `openapi.yaml`.
- **Fase 2, archivos y secretos.** Sin nómina, destajo, captura sin conexión ni evidencia; sin archivos; ninguna credencial ni ruta de usuario en el diff.
- **Contrato.** Rutas y códigos solo del borrador OpenAPI; ninguna regla `RN-xx` inventada.

## Hallazgos fuera de alcance (entrega b)

| Archivo | Observación | Prioridad |
|---|---|---|
| `frontend/src/modulos/proveedores/catalogo/PantallaProveedores.tsx` | `alAccion={() => undefined}` del alta y de la edición descarta cualquier acción: es la decisión H-1. Revisarlo si un ticket de backend añade `VER_PROVEEDOR`. | Baja |
| `backend/cimenta/proveedores/interfaz.py` | Sigue vacía; publicar ahí la normalización del RFC cuando otro código la necesite. | Baja |
| `docs/05-tickets-trabajo.md` | La frase «La pantalla del catálogo y el escenario 1 son de TKT-032» quedó desfasada tras la partición; la ajusta `/sdd-completar`. | Baja |
| `frontend/node_modules` | Sigue incompleto; ver «Entorno de ejecución». | Media: acción de la persona dueña |
| `frontend/src/modulos/proveedores/catalogo/PantallaProveedores.tsx` | Decisión de la persona dueña (2026-11-18): el alta y la edición no ofrecen «Reintentar» ni conservan lo capturado cuando responden `409` `CONCURRENCIA` (`BLOQUEO_VENCIDO`). Cierran el formulario, avisan en la cabecera y lo capturado se pierde. Se acepta tal cual; sin ticket. | Cerrada |
| `frontend/src/modulos/proveedores/catalogo/useOperacionDeEstado.ts` | La función `esBloqueo` existe copiada también en `frontend/src/compartido/formularios/FormularioCatalogo.tsx`; exportar una sola y reutilizarla toca un componente compartido, fuera del alcance de este ticket. | Baja |

## Documentación actualizada (entrega b)

| Documento | Qué cambió |
|---|---|
| `docs/arranque-local.md` | Un párrafo con el sembrador `semilla_orden_proveedor_local`, sus tres variables y sus dos líneas de salida. |
| `sdd/tickets/tkt-032a/design.md` | Filas F7 a F10 en «Hecho», tres ajustes nuevos y el prefijo `EEE` del RFC de prueba en TC-E1. |

`python tools/verificar_docs.py` → «✓ Sin problemas», con el aviso informativo de CRLF en 16 archivos.

## Verificación de la entrega b

- [x] Criterios `[M]` de la entrega b cumplidos con evidencia
- [x] Ciclo TDD completo en cada fila: rojo antes de verde, ningún test editado por un desarrollador (la prueba corregida en F7 la cambió el tester)
- [x] Suite del cliente (925 al cerrar la ejecución; 931 tras la revisión), extremo a extremo (10) y pruebas de backend afectadas (49) en verde
- [x] Al menos un test de rechazo por regla implicada
- [x] Mutación en rutas de permiso y estado (`M-6`, `M-7`), con huellas y `git status` idénticos
- [x] Auditoría de arquitectura `APROBADO`
- [x] Documentación afectada actualizada en el mismo cambio
- [x] `ruff`, `mypy`, `lint-imports`, `verificar_float`, lint y typecheck limpios
- [x] Rama `tkt-032a-pantalla-proveedores`, sin secretos en el diff

## Verificación final · entrega b

Corrida del 2026-11-18 por el orquestador en `/sdd-revisar`, con Docker respondiendo (`docker info` da 29.9.3), sobre la copia sincronizada de `frontend/` y la raíz del repositorio. Las cifras se copian de la salida de esa corrida, que es la posterior al ciclo de corrección.

```text
Cliente (vitest):             Test Files  39 passed (39)  ·  Tests  931 passed (931)
Extremo a extremo (playwright):  10 passed (24.8s)
Backend afectado (pytest):    49 passed in 15.58s
```

`npm run lint` y `npm run typecheck` terminan sin salida de error; `npm run tipos:verificar` da «Tipos al día». Desde `backend/`: `lint-imports` «Contracts: 16 kept, 0 broken», `ruff check .` «All checks passed!», `mypy .` «Success: no issues found in 376 source files» y `verificar_float` «archivos revisados: 42; hallazgos: 0». `python tools/verificar_docs.py` termina con «✓ Sin problemas» y `python -m unittest discover -s tools/tests` con 518 pruebas en OK. El E2E se corrió antes de añadir el último comentario de una línea del spec (F007), que no cambia comportamiento.

| Criterio | Nivel | Resultado |
|---|---|---|
| `CA-1` a `CA-4`, `CA-R1` | `[M]` | Cumplido (entrega a) |
| `CA-5` a `CA-8`, `CA-10`, `CA-11` | `[M]` | Cumplido, con la evidencia de «Resultado contra los criterios de aceptación (entrega b)» |
| `CA-9` | `[M]` | Cumplido |
| `CA-R2`, `CA-R3`, `CA-R4` | `[M]` | Cumplido |

**Ciclo de corrección 1 de la entrega b.** `auditor-codigo` pidió cambios (1 Mayor y 9 Menores) y `auditor-docs` otros cinco Menores; `auditor-arquitectura` y `auditor-seguridad` dieron `APROBADO` a la primera. El Mayor era una rama alcanzable sin prueba: un `409` `CONCURRENCIA` del `PATCH` cierra la edición y se pierde lo capturado. Se fijó con una prueba el comportamiento actual (no se cambió) y la decisión de ofrecer «Reintentar» quedó para la persona dueña. El tester añadió 6 pruebas y limpió el E2E (espera real de la búsqueda, tiempo del test, folio exacto), todo con la salida en `rojo/correccion-b1.txt`; el corrector extrajo `useOperacionDeEstado.ts`, fusionó los dos avisos de bloqueo en `avisarYCerrar` y corrigió la premisa falsa del diseño sobre el `409`. Un Menor de comentario (F007) persistió en la primera reauditoría, se corrigió con el texto literal y se reauditó con `haiku`: `Resuelto`.

| Auditor | Veredicto final | Ciclos |
|---|---|---|
| `auditor-arquitectura` | `APROBADO` | 1 |
| `auditor-seguridad` | `APROBADO`, con 3 observaciones Baja | 1 |
| `auditor-codigo` | `APROBADO` tras el ciclo 1 y una reauditoría acotada | 2 |
| `auditor-docs` | `APROBADO` tras el ciclo 1 | 2 |
| `auditor-sql` | No aplica | — |

**Desviaciones.** `PantallaProveedores.tsx` quedó en 276 líneas y no por debajo de 260 (el resto es JSX y estado de filtros); la copia local de `esBloqueo` no se unificó con la de `FormularioCatalogo.tsx` porque es un componente compartido fuera del alcance. Ninguna cambia el alcance.

**Decisión de la persona dueña (2026-11-18).** El alta y la edición se quedan como están ante un `409` `CONCURRENCIA`: el formulario se cierra, se avisa en la cabecera y lo capturado se pierde; no se ofrece «Reintentar». No hay ticket pendiente por este motivo.

**Pendiente.** (1) `frontend/node_modules` sigue incompleto. (2) Los verificadores que solo corren con el pipeline de un PR real (los nueve trabajos de `ci.yml` y la comprobación «Etiqueta de origen») se verifican en `/sdd-completar`.
