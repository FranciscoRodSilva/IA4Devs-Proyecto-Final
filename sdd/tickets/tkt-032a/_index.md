# TKT-032a · Pantalla del catálogo de proveedores

> Hub del ticket. Se lee **primero**, siempre.

## Estado

ARCHIVADO · las dos entregas (a: F1 a F6 sin F3; b: F7 a F10) se fusionaron juntas en el PR #82. La planificación queda archivada. El PR se fusionó con una excepción aprobada por la persona dueña: la comprobación de dependencias estaba en rojo por avisos de `npm audit` ajenos al ticket (`hono` y `minimatch`, de severidad moderada), y el PR no cambia dependencias. El despliegue es un evento posterior.

## Ficha

| | |
|---|---|
| **Tipo** | Funcionalidad |
| **Historia** | [[HDU-004]] — escenarios 1, 2, 3, 12 y 13 |
| **Épica / sprint** | HDU-004 · Orden de compra a proveedor, fase 1 (la pantalla del catálogo se adelanta por la entrega 3) |
| **Puntos** | Talla M en el backlog (TKT-032, partido en 032a y 032b) |
| **Reglas implicadas** | `RN-17`; `RN-15` y `RN-16` solo como contexto (v1.1); `PA-24` abierta |
| **Invariantes en riesgo** | Ninguno de backend; regresión de rutas protegidas, de los componentes de TKT-008c y del contrato publicado |
| **Módulos en alcance** | Frontend: `modulos/proveedores` y componentes compartidos. Sin módulo de backend |
| **Capas en alcance** | frontend. Sin backend ni migración |
| **Criterios `[M]`** | `CA-1` a `CA-11`, `CA-R1` a `CA-R4` |
| **Depende de** | TKT-029a y TKT-029b (ARCHIVADOS), TKT-008 (ARCHIVADO) |
| **Rama** | `tkt-032a-pantalla-proveedores` (sale de `Produccion`) |

## Artefactos

| Artefacto | Enlace | Comando | Estado |
|---|---|---|---|
| Spec | [spec.md](spec.md) | `/sdd-definir` | Escrita el 2026-11-17 |
| Design | [design.md](design.md) | `/sdd-disenar` | Escrito el 2026-11-17, aprobado el 2026-11-17 |
| Impl | [impl.md](impl.md) | `/sdd-ejecutar` | Entregas a y b escritas |
| Delta | [delta.md](delta.md) | `/sdd-completar` | Escrito el 2026-11-18 |
| PR | [#82](https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final/pull/82) | `/sdd-completar` | Fusionado el 2026-11-18 |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-11-17 | — | `SPEC PENDIENTE` | `/sdd-definir` | Spec creada. TKT-032 partido en TKT-032a (pantalla del catálogo, solo frontend) y TKT-032b (consulta por obra, emisión y cancelación, que dependen de TKT-030 y TKT-031). Must validado por la persona dueña: lista, alta, edición, desactivar y baja con su `409`, más una prueba de extremo a extremo. 11 criterios `[M]` y 4 de regresión; rechazos de RFC duplicado, forma por campo, baja con órdenes, transición ya no válida, rol y sesión. Cinco preguntas abiertas con recomendación, entre ellas que no existe wireframe del catálogo. INVEST: cero fallos, reserva en E. La pasada adversarial la hizo quien redactó, no la skill |
| 2026-11-17 | `SPEC PENDIENTE` | `DISEÑO PENDIENTE REVISIÓN` | `/sdd-disenar` | Design escrito: 10 filas en dos entregas (a: boceto, extensiones compartidas, lista y alta; b: edición, desactivar, baja y bloqueos, contrato y extremo a extremo), solo frontend más un sembrador local en `backend/herramientas/`. Escalera sin objeto en el peldaño 4 sobre un invariante. `revisor-impacto`: sin frontera cruzada y ocho hallazgos incorporados (uno bloqueante: la etiqueta `DESACTIVAR_PROVEEDOR` rompe cuatro líneas de una prueba de TKT-008c, ahora D-10). Pasada adversarial con la skill: siete objeciones. Esperan a la persona dueña: boceto de F1, D-6 a D-10, y para `/sdd-escalar` H-1 (el contrato no trae la acción de ver al proveedor duplicado) y H-2 (el E2E exige un archivo nuevo en `backend/herramientas/`). El gate del estado se leyó como `SPEC LISTA PARA DISEÑO`, no `SPEC PENDIENTE`: mismo significado, el hub lo cambió el definir |
| 2026-11-17 | `DISEÑO PENDIENTE REVISIÓN` | `LISTO PARA EJECUTAR` | `/sdd-disenar` | La persona dueña aprobó el diseño completo en la conversación principal: todas las recomendaciones del diseño, incluidos H-1 (`CA-3` sin acción de verlo) y H-2 (sembrador local de pruebas); `/sdd-escalar` no hace falta |
| 2026-11-17 | `LISTO PARA EJECUTAR` | `EN REVISIÓN · entrega a` | `/sdd-ejecutar` | Entrega a (F1 a F6) ejecutada con TDD: F1 boceto 2c, F2 etiquetas, F3 eliminada porque TKT-012b ya trajo `soloLectura`, F4 consultas y esquemas, F5 lista y rutas, F6 alta. Suite del cliente en verde (859 pruebas), mutantes M-1 a M-5 caídos, `auditor-arquitectura` `APROBADO` con tres observaciones. Quedan la entrega b (F7 a F10) y arreglar `frontend/node_modules`, que un `npm ci` fallido dejó incompleto por un servidor de desarrollo abierto |
| 2026-11-18 | `EN REVISIÓN · entrega a` | `LISTO PARA EJECUTAR · entrega b` | `/sdd-revisar` | Entrega a revisada y acumulada en la rama, sin PR. Suite del cliente en verde (863 pruebas tras el ciclo), lint, typecheck y verificadores de documentos limpios. `auditor-arquitectura` y `auditor-seguridad` `APROBADO`; `auditor-codigo` y `auditor-docs` pidieron cambios (un Mayor cada uno, más Menores) y quedaron `APROBADO` tras un ciclo de corrección. La corrección añadió cuatro pruebas, extrajo `totalDePaginas`, marcó la baja terminal `(asumido, PA-24)` y quitó rutas locales de la evidencia. Siguiente: `/sdd-ejecutar` sobre la entrega b |
| 2026-11-18 | `LISTO PARA EJECUTAR · entrega b` | `EN REVISIÓN · entrega b` | `/sdd-ejecutar` | Entrega b (F7 a F10) ejecutada con TDD: edición, desactivar, dar de baja y bloqueos, prueba de contrato y recorrido de extremo a extremo con una orden `PARCIAL` real y su sembrador local (H-2). Cliente 925 pruebas, E2E 10 de 10, backend afectado 49, lint, typecheck, `tipos:verificar` y verificadores limpios; mutantes `M-6` y `M-7` caídos; `auditor-arquitectura` `APROBADO`. El rojo de F9 nació en verde, justificado con cinco mutantes. Siguiente: `/sdd-revisar` sobre la entrega b |
| 2026-11-18 | `EN REVISIÓN · entrega b` | `LISTO PARA PR` | `/sdd-revisar` | Entrega b revisada. Cliente 931 pruebas, E2E 10 de 10, backend afectado 49, lint, typecheck, `tipos:verificar` y verificadores limpios. `auditor-arquitectura` y `auditor-seguridad` `APROBADO`; `auditor-codigo` (1 Mayor y 9 Menores) y `auditor-docs` (5 Menores) pidieron cambios y quedaron `APROBADO` tras un ciclo; un Menor de comentario se reauditó con `haiku`. El Mayor fue una rama de `409` `CONCURRENCIA` del `PATCH` sin prueba: se fijó el comportamiento actual con una prueba y la decisión de ofrecer «Reintentar» queda para la persona dueña. Siguiente: `/sdd-completar TKT-032a` |
| 2026-11-18 | `LISTO PARA PR` | `PENDIENTE FUSIÓN` | `/sdd-completar` | Cierre del ticket: `delta.md` escrito, documentación auditada (un Mayor de markdownlint en `design.md:71` y cinco Menores, resueltos), nueve filas de evolución y propuestas de `meta-sdd` sin aplicar, y el hub archivado dentro del PR. La frase desfasada de TKT-029 en `docs/05-tickets-trabajo.md` ahora apunta a TKT-032a. Siguiente: commit, PR y aprobación de la fusión |
| 2026-11-18 | `PENDIENTE FUSIÓN` | `ARCHIVADO` | `/sdd-completar TKT-032a` | PR #82 fusionado en `Produccion` (commit `9d82438`) con nueve de las diez comprobaciones requeridas en verde sobre `2dda490`; la de «Dependencias · auditoría de vulnerabilidades» estaba en rojo por avisos de `npm audit` ajenos al ticket y la persona dueña aprobó fusionar con esa excepción. `Produccion` no tiene protección de rama, así que la fusión fue un merge normal atado al SHA, sin `--admin`, con comentario de registro en el PR. La planificación queda archivada |

## Decisiones registradas

- 2026-11-17 · La persona dueña resolvió D-1 y D-3: el diseño dibuja el wireframe del catálogo y reconcilia la baja en `docs/08-wireframes.md`; el E2E siembra una orden `PARCIAL` con `sembrar_orden_compra` para probar el `409` de la baja.
- 2026-11-17 · La persona dueña validó la partición de TKT-032: **TKT-032a** es solo la pantalla del catálogo; la consulta proveedor × obra (esc. 11), la emisión y la cancelación pasan a **TKT-032b**, que sigue dependiendo de TKT-030 y TKT-031.
- 2026-11-17 · La persona dueña aprobó el boceto de F1 (catálogo de proveedores y reconciliación de la baja) y las decisiones D-6 a D-10 con su recomendación: mensaje del `403` del servidor, «Editar» en `ACTIVO` y `DESACTIVADO`, acciones de estado por fila, conflicto de RFC bajo los campos y cambio declarado de cuatro líneas de una prueba de TKT-008c. H-1 y H-2 siguen abiertos.

- 2026-11-17 · La persona dueña resolvió H-1 y H-2 en la conversación principal: `CA-3` muestra el proveedor existente sin acción de verlo, y se aprueba el sembrador local `backend/herramientas/semilla_orden_proveedor_local.py` como apoyo de pruebas.
- 2026-11-18 · La persona dueña decidió, en `/sdd-revisar` de la entrega b, dejar el alta y la edición como están ante un `409` `CONCURRENCIA`: el formulario se cierra, se avisa en la cabecera con el mensaje y la referencia, y lo capturado se pierde; no se ofrece «Reintentar».

## Tickets futuros sugeridos

- **TKT-032b** · consulta proveedor × obra, emisión y cancelación de órdenes (depende de TKT-030 y TKT-031).
- Reactivar un proveedor `DESACTIVADO` o dado de `BAJA` (`PA-24`).
- **VER_PROVEEDOR** · añadir la acción de ver al proveedor existente en el `409` `RFC_DUPLICADO` (backend, `openapi.yaml` y pruebas de TKT-029a).
- Extraer `EsqueletoLista` y `AvisoErrorLista` y la copia de `esBloqueo` a `compartido/`, ahora que TKT-012b está fusionado.
