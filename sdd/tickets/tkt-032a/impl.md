# Impl · TKT-032a · Pantalla del catálogo de proveedores

> [← index](_index.md) | [← design](design.md) | Siguiente: `delta.md` (se enlaza en `/sdd-completar`)

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
| 2026-11-17 | Un `alBloqueo` del alta cierra el formulario y pinta un aviso de cabecera con el mensaje y la referencia. | El endpoint `POST /proveedores` no declara ningún `409` de regla ni `CONCURRENCIA`, así que es una rama defensiva. La fila F8 lo sustituye por `PantallaBloqueo`. |
| 2026-11-17 | El RFC en minúsculas se normaliza a mayúsculas y se acepta. | El servidor hace la misma normalización; la tabla de entradas hostiles del diseño decía «minúsculas» entre lo rechazable y el texto del esquema decía «recortado y en mayúsculas». Se siguió el texto del esquema. |

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
| `sdd/tickets/tkt-032a/rojo/fila-2.txt`, `fila-4.txt`, `fila-5.txt`, `fila-6.txt` | nuevo: salida literal de cada rojo | evidencia |

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

**Resumen de la salida del verde de cierre de la entrega** (corrida por el orquestador, con Docker respondiendo, sobre la copia sincronizada del repositorio):

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
| `auditor-arquitectura` | `APROBADO` | 0 críticos, 0 mayores, 0 menores y 3 observaciones sin acción | 1 |
| `auditor-sql` | No aplica | La entrega no tiene esquema ni migración | — |

### Hallazgos y su resolución

| ID | Auditor | Severidad | Ubicación | Hallazgo | Estado |
|---|---|---|---|---|---|
| O-1 | `auditor-arquitectura` | Observación | `PantallaProveedores.tsx`, `alAccion` del alta | `alAccion` es una función vacía: hoy `RFC_DUPLICADO` llega sin acciones (H-1). Si un ticket de backend añade `VER_PROVEEDOR`, habrá que revisarlo. | Aceptado: es la decisión H-1 |
| O-2 | `auditor-arquitectura` | Observación | `PantallaProveedores.tsx`, botones de fila | Los botones Editar, Desactivar y Dar de baja se pintan sin acción hasta la entrega b. No fusionar la entrega a sola. | Aceptado: un solo PR por ticket, se abre al aprobarse la entrega b |
| O-3 | `auditor-arquitectura` | Observación | `PantallaProveedores.tsx` y `proveedores.consultas.ts` | `TAMANO_PAGINA = 50` está duplicado en dos archivos. | Se resuelve en la entrega b si toca esos archivos; si no, queda anotado |

### Qué verificó el auditor (copiado de su informe)

- **Dinero nunca flotante.** `grep` por `Number(`, `parseInt`, `parseFloat`, `toFixed` e import directo de `decimal.js` en `modulos/proveedores`: sin coincidencias. El tope entra y sale como cadena y `cambiosDe` compara con `Decimal.eq` vía `@/compartido/dinero/dinero`. Un mutante propio (tope por `parseFloat`) hizo caer 13 pruebas.
- **El cliente nunca decide una regla.** Las acciones por fila salen del `estado` que devolvió el servidor; ninguna acción de bloqueo está cableada; `etiquetas.ts` solo añade rótulos. Dos mutantes propios cayeron (`BAJA` con acción y `puedeOperar` verdadero).
- **Fronteras de módulo.** El módulo del cliente solo importa de `@/api`, `@/components/ui`, `@/compartido` y de la guarda y la tabla de secciones de `@/app`; ningún otro módulo de `modulos/`.
- **Fase 2 y backend.** Sin captura sin conexión, evidencia, nómina ni destajo. Sin cambios a `cimenta/`, `migraciones/` ni `docs/api/openapi.yaml`.
- **Obras y pruebas de TKT-008c.** `PantallaObras.tsx` no figura en el diff. `FormularioCatalogo.test.tsx` cambia exactamente las cuatro líneas de D-10; `PantallaBloqueo.test.tsx` y `ConflictoEnLinea.test.tsx` solo suman líneas.
- **Secretos, contrato de error y camino no feliz.** Sin secretos; ningún `RN-xx` inventado; rechazos para cada `422`, `RFC_DUPLICADO`, `403`, rol sin sección, sin sesión, y errores de la lista.
- **Máquina.** Lint y typecheck limpios; 36 archivos y 859 pruebas en verde; `verificar_docs.py` sin problemas y `markdownlint-cli2` con 0 problemas.

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

`python tools/verificar_docs.py` → sin problemas una vez existe este archivo; queda el aviso informativo de que 15 archivos tienen CRLF en la copia de trabajo, que Git normaliza.

## Verificación de la entrega

- [x] Criterios `[M]` de la entrega a cumplidos con evidencia (los parciales están señalados)
- [x] Ciclo TDD por fila: rojo antes de verde, ningún test editado por un desarrollador (el único cambio a una prueba existente es D-10, hecho por el tester)
- [x] Suite del cliente en verde: 859 pruebas
- [x] Al menos un test de rechazo por regla implicada
- [x] Mutación en rutas de permiso y de estado, con huellas y `git status` idénticos
- [x] Auditoría de arquitectura `APROBADO`
- [x] Documentación afectada actualizada en el mismo cambio
- [x] Lint y typecheck limpios
- [x] Sin secretos en el diff; rama `tkt-032a-pantalla-proveedores`
