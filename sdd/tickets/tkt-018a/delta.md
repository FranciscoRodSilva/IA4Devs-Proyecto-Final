# Delta · TKT-018a · Pantalla de línea base y presupuesto de control

> [← index](_index.md) | [← impl](impl.md)

El ticket se ejecutó en tres entregas sobre una sola rama y se cierra con un solo pull request. Cada entrega aportó lo siguiente:

- **Entrega a** · línea base y congelado (filas A1 a A5): la pantalla `/obras/:obraId/linea-base` con la línea base de la obra y el formulario de congelado con motivo, el enlace desde la lista de obras y las dos entradas del menú que remiten a «Obras».
- **Entrega b** · presupuesto de control (filas B1 a B4): la captura de los topes por tipo de partida, con éxito parcial, la confirmación del tope superior a la venta y la recaptura con motivo, más la documentación de los bocetos.
- **Entrega c** · semilla local y prueba de extremo a extremo (filas C1 y C2, *Should*): una herramienta que siembra una obra con su línea base `BORRADOR` en la base local y el recorrido de Playwright que congela y captura un tope.

No hay backend, migración ni contrato nuevos: la pantalla consume cinco operaciones que TKT-017 y TKT-012a ya publicaban.

## Añadido

| Qué | Dónde | Para qué |
|---|---|---|
| Pantalla de línea base: `PantallaLineaBase`, `FormularioCongelado`, `ElegirObra`, `linea-base.consultas.ts`, `presentacion.ts` | `frontend/src/modulos/presupuesto/linea-base/` | Mostrar la línea base de la obra de la ruta (versión, estado, importe de venta, desglose por tipo de partida, y autor, fecha y motivo del congelado) y congelarla con motivo (`RN-01`) |
| `TablaPresupuestoControl`, `DialogoRecaptura` y `tope.formulario.ts` | Misma carpeta | Capturar y recapturar el tope de control por tipo de partida (`RN-03`, `RN-04`, `PA-03`), con `PUT` secuenciales, éxito parcial, confirmación del tope superior a la venta y validación de forma del importe |
| Ruta `/obras/:obraId/linea-base` y columna «Línea base» con el enlace por obra | `modulos/presupuesto/rutas.tsx` y `obras/PantallaObras.tsx` | Dar la obra de contexto por la URL, sin selector de obra |
| Semilla local `semilla_linea_base_local.py` y sus cinco pruebas, más seis del ciclo de corrección | `backend/herramientas/` y `backend/tests/test_tkt018a_semilla_linea_base.py` | Poder ver la pantalla con una línea base real mientras no exista la importación (TKT-018b) |
| Recorrido E2E `linea-base.spec.ts` y el usuario de humo de Dirección General | `frontend/e2e/` | Probar de punta a punta que un Director de Proyectos congela y una persona de Dirección General captura un tope |
| Fábricas de prueba `lineaBase`, `filaControl`, `controlSinTopes`, `obra` y los cuerpos de error del congelado | `frontend/src/pruebas/cuerpos.ts` | Cuerpos fieles al backend en las pruebas de rechazo |
| `obraOptions` | `modulos/presupuesto/obras/obras.consultas.ts` | Leer una obra por su identificador para la cabecera de la pantalla |

## Modificado

| Qué | Dónde | Antes → después |
|---|---|---|
| Entradas «Línea base» y «Presupuesto de control» del menú | `modulos/presupuesto/rutas.tsx` | «Esta sección aún no está disponible» → remiten a «Obras» con un enlace, sin cambiar de ruta ni de tabla de secciones |
| `CapturaMotivo` | `compartido/formularios/` | Botón de salida siempre «Cancelar» → prop opcional `etiquetaCancelar`, y salida deshabilitada mientras el envío está en vuelo |
| Rótulos del bloqueo | `compartido/componentes/bloqueo/etiquetas.ts` | Claves `version_vigente`, `estado_obra`, `importe_venta` y `importe_tope` sin rótulo → con rótulo; los identificadores internos de la línea base se ocultan y `causas` se pinta como tabla |
| `DetalleCifras` | `compartido/componentes/bloqueo/` | Una celda `null` se pintaba «null» → se pinta vacía; un espacio entre etiqueta y valor para el texto accesible |
| Pruebas existentes de TKT-012a y del bloqueo | `PantallaObras.test.tsx` (la fábrica `obra` pasa a `pruebas/cuerpos.ts`), `ConflictoEnLinea.test.tsx` (importaciones y bloque TC-04) y `PantallaBloqueo.test.tsx` (casos nuevos) | Reorganizadas o ampliadas; ningún caso anterior se eliminó y la suite completa sigue en verde |
| Preparación global del humo | `frontend/e2e/preparacion-global.ts` | Dos usuarios de humo → tres, más una obra con línea base `E2E-LB-<8 hex>` por corrida |
| Docstring de `soporte_tkt017.py` | `backend/herramientas/` | Solo ayudantes de prueba de TKT-017 → también lo usa la semilla local |
| Bocetos 2, 2b, 3, 4, 4a, 4b, 12 y 13 | `docs/08-wireframes.md` | Ver «Contrato público tocado»; la pantalla 4 pasa a TKT-018a y la 3 a TKT-018b |
| Guía de arranque | `README.md`, `docs/arranque-local.md` | Cómo sembrar una línea base de demostración y qué siembra el E2E |

## Eliminado

| Qué | Dónde | Por qué era seguro quitarlo |
|---|---|---|
| Aviso en línea «! mayor que la venta» del boceto 4b | `docs/08-wireframes.md` | Exigía comparar tope y venta en el cliente, y el cliente nunca evalúa una regla (regla 10 de `CLAUDE.md`); lo decide el `409` del servidor (`D-10`) |
| «Importada el … por …», el conteo de conceptos y los botones «Ver conceptos» y «Ver explosión» del boceto 4a | `docs/08-wireframes.md` | El contrato de `LineaBase` no trae esos datos; quedan anotados como futuros |

## Comportamiento observable nuevo

- Director de Proyectos, Dirección General y Compras abren «Línea base» desde la lista de obras y ven la línea base `CONGELADA` de la obra o, si no la hay, el `BORRADOR` de mayor versión. Compras no ve el borrador (presentación, no seguridad; el servidor sí se lo devuelve).
- El Director de Proyectos congela el borrador con motivo obligatorio. La obra pasa a `ACTIVA`. Los rechazos se pintan con el contrato de error: `RN-01` (segunda línea base vigente), estado que no lo permite, `CONCURRENCIA` con cuenta atrás y reintento, `403` y `404`.
- Dirección General captura el tope de cada tipo de partida en la propia tabla, sin motivo la primera vez (`PA-03`). Si el servidor responde que el tope supera la venta, se abre una confirmación con motivo («Confirmar con motivo» o «Corregir»). Si una fila se rechaza, las demás se guardan y un resumen dice cuáles.
- Dirección General recaptura un tope ya fijado con tope nuevo y motivo; queda en la bitácora de excepciones. El resto de los roles ve el tope en lectura.
- Quien siembre la base local puede crear una obra con su línea base `BORRADOR` con `herramientas.semilla_linea_base_local`.

## Contrato público tocado

| Superficie | Cambio | ¿Rompe compatibilidad? |
|---|---|---|
| Endpoints, DTO, tipos generados, esquema | Ninguno. `git diff` de `docs/api/openapi.yaml`, de `frontend/src/api/generado` y de `backend/cimenta` está vacío en las tres entregas | No |
| `CapturaMotivo` (componente compartido) | Prop opcional `etiquetaCancelar`; el valor por omisión es el de antes y sus 14 pruebas no se modificaron | No |
| Documentación de pantallas (`docs/08-wireframes.md`) | Los endpoints `GET /lineas-base/{id}`, `/conceptos` y `/explosion` salen de la lista de la pantalla 4 porque esta entrega no los usa; `RN-18` pasa a `F1.6` en el boceto 4b | No |

## Decisiones (ADR)

Ningún ADR nuevo en este ticket. `D-1`, `D-7`, `D-10` y `D-11` son de presentación y `D-6` es de orden de trabajo. `D-5` (un `PUT` secuencial por fila con éxito parcial, en lugar de una ruta por lotes que exigía backend nuevo) descartó una alternativa, y por eso `auditor-docs` pidió un ADR o su descarte por escrito. El 2026-11-11 la persona dueña decidió no escribirlo: la decisión es de presentación del cliente, no cambia el contrato, ya está aprobada y justificada en `design.md` y la prueban las pruebas del éxito parcial (TC-23 y TC-29); un ADR obligaría además a actualizar los conteos de ADR de la documentación.

## Aprendizajes

| Aprendizaje | Evidencia | Dónde aplica |
|---|---|---|
| Un filtro redundante no se mata con la variante obvia: el filtro `importe_tope === null` de «Guardar topes» es redundante con el filtro por valor vacío en un único guardado; solo lo mata un segundo guardado, porque el formulario conserva lo escrito | Mutante `M-2` y la variante «dos guardados seguidos» de TC-23 | Cualquier formulario con filas que se guardan por partes |
| Con un diálogo de Radix abierto, `main` queda con `aria-hidden` y `getByRole` ya no ve la tabla de debajo; se lee la fila con un selector que no filtra por accesibilidad | Helper `filaTrasElDialogo` de `TablaPresupuestoControl.test.tsx` | Pruebas de pantallas con diálogo sobre una tabla |
| Una acción que reenvía un `PUT` desde un bloqueo en línea debe reenviar lo que provocó el `409`, no los valores actuales del formulario, y debe cerrar el paso a un segundo envío mientras está en vuelo | `COD-3` y `F002`; mutantes de reentrada | Cualquier confirmación o reintento tras un rechazo con `acciones` |
| `spawnSync` de Node devuelve `stdout` y `status` en `null` si no puede lanzar el proceso (`ENOENT`); hay que mirar `error` y `status` antes de leer `stdout` | `COD-1` y la prueba manual de la reauditoría | Los scripts de preparación de los E2E |
| `Dialog` y `CapturaMotivo` funcionan en jsdom con el reloj simulado, y un `PUT` retenido con una promesa permite probar el estado «en vuelo» sin esperas por tiempo | Pruebas de `COD-1`, `COD-4` y `F002` | Pruebas de acciones en vuelo |

## Observaciones para `_evolucion.md`

| Tema | Observación | Severidad |
|---|---|---|
| `agente` | El rojo de C1 salió por módulo ausente y `tester-backend` no puede crear un esqueleto (su rol no escribe producción): lo creó el orquestador. Falta decir en `tester-backend` o en `/sdd-ejecutar` quién crea el esqueleto no funcional cuando el módulo no existe | Media |
| `herramienta` | Un límite de uso de la cuenta cortó las cuatro auditorías en paralelo de `/sdd-revisar` (entrega c); hubo que relanzarlas de cero, a diferencia de TKT-012a, donde `SendMessage` reanudó al agente | Baja |
| `guardrail` | Los auditores de solo lectura dejaron efectos en la base local: `contrasenas_roles` cambió las contraseñas de los roles y una reauditoría sembró un usuario `x@y.z`. La regla «solo lectura» no distingue entre el repositorio y la base local de desarrollo | Media |
| `herramienta` | `frontend/test-results/.last-run.json` está versionado y Playwright lo reescribe en cada corrida; se restauró a mano tres veces. Conviene ignorarlo | Baja |
| `agente` | El `impl.md` de cada entrega cita cifras que el ciclo de corrección cambia (cinco pruebas de la semilla pasaron a once; 2772 a 2778); la «Verificación final» las sustituye, pero la sección de la entrega queda desactualizada hasta entonces | Baja |
| `agente` | `auditor-codigo` encontró defectos de concurrencia de interfaz (cola de confirmaciones, segundo envío en vuelo) en dos ciclos seguidos, no en la primera pasada. Una lista de comprobación de «acción en vuelo» en el diseño o en `tester-frontend` los habría adelantado | Media |
| `herramienta` | Los archivos editados desde Windows llegaron a la revisión con CRLF y `git` avisó «CRLF will be replaced by LF» en cinco archivos | Baja |
| `comando` | Tres entregas en una sola jornada funcionaron con una rama y un PR; el disparador de recorte fechado de la entrega c (el cierre del 2026-11-11) no hizo falta, pero obligó a medir el tiempo desde la entrega b | Baja |

## Deuda que queda abierta

| Qué | Por qué se dejó | Ticket sugerido |
|---|---|---|
| Marcador `(aprobado · D-7)` en `docs/08-wireframes.md` §2 | Decisión de la persona dueña: conservarlo o quitarlo | — |
| `F001`: la semilla crea la obra y la importación con `INSERT` directo y sin asiento de bitácora, porque `crear_obra` no está en la interfaz publicada de `presupuesto` | Solo afecta a la base local; no había camino por la interfaz | TKT-018b o un ticket que publique `crear_obra`, para migrar la semilla |
| `SEG-1` (entrega c, guarda de base local sin puerto: un túnel `ssh -L` la pasa), `SEG-2` (entrega c, falta `hide_parameters` en `sembrar_usuario_humo.py`) y `SEG-3` (entrega c, el trazado de Playwright registra las contraseñas aleatorias de cada corrida) | Previas a este ticket y de gravedad Baja | Un ticket de endurecimiento de las herramientas de humo |
| Observaciones de `auditor-codigo`: `recapturando` guarda la fila y no su identificador; `enviarTopes` no se cancela al desmontar; las acciones del bloqueo en línea siguen habilitadas mientras envían; el selector `getByLabel("Tope de MUROS")` sin `exact`; `spawnSync` sin tiempo máximo; el mutante `slice(1)` de la cola sobrevive porque las guardas lo hacen inalcanzable | No cambian el comportamiento observable | Un ticket de pulido de la pantalla |
| Hallazgos de `code-review` (nivel alto) sobre la rama, sin aplicar: «Confirmar el tope» de la recaptura reenvía los valores que provocaron el `409` y no los que el formulario muestra tras editarlos (decisión de `COD-3`; convendría bloquear los campos mientras haya bloqueo en línea); la siembra local no es atómica (la preparación y la confirmación son dos transacciones, así que un fallo de `materializar_importacion` deja la obra y quema el código); el bucle de `PUT` no se corta ante un `403` ni al desmontar; `autorYFecha` resuelve autor y fecha por separado; un refetch fallido con datos cargados es silencioso; tres copias del reparto de errores de validación; marcado duplicado de autor y fecha | Cambian el pulido y no el comportamiento observable de la entrega, y varios son decisiones ya tomadas en `COD-3` y `COD-5` | Un ticket de pulido de la pantalla y de las herramientas de humo |
| Las tablas «Ver conceptos» y «Ver explosión por tipo de partida» del boceto 4a, con su paginación | Won't de la spec | A partir de TKT-018b |
| Selector de obra del armazón (boceto 2) | Won't de la spec | Un ticket de armazón |
| «Quién importó y cuándo, con los conteos de conceptos e insumos» del boceto 4a | El contrato de `LineaBase` no los trae; exigiría ampliarlo en el backend | TKT-018b |
| El flujo de importación completo y la deuda de TKT-017 que va con él | Dividido de este ticket por el plazo | TKT-018b |
| Sin TKT-018b, la pantalla solo se ve con línea base real mediante la semilla local | La importación no existe todavía | TKT-018b |

## Pull request

**Título:** `TKT-018a · Pantalla de línea base y presupuesto de control`
**Origen:** `agent`. El código lo escribieron agentes y lo revisan los auditores y la persona dueña.
**Cuerpo:** qué (la pantalla de línea base con el congelado, el presupuesto de control con captura y recaptura de topes, la semilla local y el recorrido E2E); por qué (cerrar el hilo vertical de la fase 1 en la interfaz: sin tope no hay control presupuestal); criterios cubiertos (`CA-1` a `CA-13`, `CA-R1`, `CA-R2` y `CA-S1`); cómo verificarlo (Vitest 438 de 438, backend 2778 en verde con 26 omitidas, Playwright 6 de 6, y `docs/arranque-local.md` para ver la pantalla con la semilla local). Una línea por entrega: la a aporta la línea base y el congelado, la b el presupuesto de control y la recaptura, la c la semilla local y el E2E.
