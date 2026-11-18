# TKT-032a · Pantalla del catálogo de proveedores

> Hub del ticket. Se lee **primero**, siempre.

## Estado

LISTO PARA EJECUTAR · entrega b (filas F7 a F10 del diseño). La entrega a (F1 a F6, sin F3) quedó revisada y acumulada en la rama `tkt-032a-pantalla-proveedores`, sin PR.

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
| Design | [design.md](design.md) | `/sdd-disenar` | Escrito el 2026-11-17, pendiente de revisión |
| Impl | [impl.md](impl.md) | `/sdd-ejecutar` | Entrega a escrita el 2026-11-17; falta la sección de la entrega b |
| Delta | `delta.md` (se enlaza en `/sdd-completar`) | `/sdd-completar` | Pendiente |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-11-17 | — | `SPEC PENDIENTE` | `/sdd-definir` | Spec creada. TKT-032 partido en TKT-032a (pantalla del catálogo, solo frontend) y TKT-032b (consulta por obra, emisión y cancelación, que dependen de TKT-030 y TKT-031). Must validado por la persona dueña: lista, alta, edición, desactivar y baja con su `409`, más una prueba de extremo a extremo. 11 criterios `[M]` y 4 de regresión; rechazos de RFC duplicado, forma por campo, baja con órdenes, transición ya no válida, rol y sesión. Cinco preguntas abiertas con recomendación, entre ellas que no existe wireframe del catálogo. INVEST: cero fallos, reserva en E. La pasada adversarial la hizo quien redactó, no la skill |
| 2026-11-17 | `SPEC PENDIENTE` | `DISEÑO PENDIENTE REVISIÓN` | `/sdd-disenar` | Design escrito: 10 filas en dos entregas (a: boceto, extensiones compartidas, lista y alta; b: edición, desactivar, baja y bloqueos, contrato y extremo a extremo), solo frontend más un sembrador local en `backend/herramientas/`. Escalera sin objeto en el peldaño 4 sobre un invariante. `revisor-impacto`: sin frontera cruzada y ocho hallazgos incorporados (uno bloqueante: la etiqueta `DESACTIVAR_PROVEEDOR` rompe cuatro líneas de una prueba de TKT-008c, ahora D-10). Pasada adversarial con la skill: siete objeciones. Esperan a la persona dueña: boceto de F1, D-6 a D-10, y para `/sdd-escalar` H-1 (el contrato no trae la acción de ver al proveedor duplicado) y H-2 (el E2E exige un archivo nuevo en `backend/herramientas/`). El gate del estado se leyó como `SPEC LISTA PARA DISEÑO`, no `SPEC PENDIENTE`: mismo significado, el hub lo cambió el definir |
| 2026-11-17 | `DISEÑO PENDIENTE REVISIÓN` | `LISTO PARA EJECUTAR` | `/sdd-disenar` | La persona dueña aprobó el diseño completo en la conversación principal: todas las recomendaciones del diseño, incluidos H-1 (`CA-3` sin acción de verlo) y H-2 (sembrador local de pruebas); `/sdd-escalar` no hace falta |
| 2026-11-17 | `LISTO PARA EJECUTAR` | `EN REVISIÓN · entrega a` | `/sdd-ejecutar` | Entrega a (F1 a F6) ejecutada con TDD: F1 boceto 2c, F2 etiquetas, F3 eliminada porque TKT-012b ya trajo `soloLectura`, F4 consultas y esquemas, F5 lista y rutas, F6 alta. Suite del cliente en verde (859 pruebas), mutantes M-1 a M-5 caídos, `auditor-arquitectura` `APROBADO` con tres observaciones. Quedan la entrega b (F7 a F10) y arreglar `frontend/node_modules`, que un `npm ci` fallido dejó incompleto por un servidor de desarrollo abierto |
| 2026-11-18 | `EN REVISIÓN · entrega a` | `LISTO PARA EJECUTAR · entrega b` | `/sdd-revisar` | Entrega a revisada y acumulada en la rama, sin PR. Suite del cliente en verde (863 pruebas tras el ciclo), lint, typecheck y verificadores de documentos limpios. `auditor-arquitectura` y `auditor-seguridad` `APROBADO`; `auditor-codigo` y `auditor-docs` pidieron cambios (un Mayor cada uno, más Menores) y quedaron `APROBADO` tras un ciclo de corrección. La corrección añadió cuatro pruebas, extrajo `totalDePaginas`, marcó la baja terminal `(asumido, PA-24)` y quitó rutas locales de la evidencia. Siguiente: `/sdd-ejecutar` sobre la entrega b |

## Decisiones registradas

- 2026-11-17 · La persona dueña resolvió D-1 y D-3: el diseño dibuja el wireframe del catálogo y reconcilia la baja en `docs/08-wireframes.md`; el E2E siembra una orden `PARCIAL` con `sembrar_orden_compra` para probar el `409` de la baja.
- 2026-11-17 · La persona dueña validó la partición de TKT-032: **TKT-032a** es solo la pantalla del catálogo; la consulta proveedor × obra (esc. 11), la emisión y la cancelación pasan a **TKT-032b**, que sigue dependiendo de TKT-030 y TKT-031.
- 2026-11-17 · La persona dueña aprobó el boceto de F1 (catálogo de proveedores y reconciliación de la baja) y las decisiones D-6 a D-10 con su recomendación: mensaje del `403` del servidor, «Editar» en `ACTIVO` y `DESACTIVADO`, acciones de estado por fila, conflicto de RFC bajo los campos y cambio declarado de cuatro líneas de una prueba de TKT-008c. H-1 y H-2 siguen abiertos.

- 2026-11-17 · La persona dueña resolvió H-1 y H-2 en la conversación principal: `CA-3` muestra el proveedor existente sin acción de verlo, y se aprueba el sembrador local `backend/herramientas/semilla_orden_proveedor_local.py` como apoyo de pruebas.

## Tickets futuros sugeridos

- **TKT-032b** · consulta proveedor × obra, emisión y cancelación de órdenes (depende de TKT-030 y TKT-031).
- Reactivar un proveedor `DESACTIVADO` o dado de `BAJA` (`PA-24`).
- **VER_PROVEEDOR** · añadir la acción de ver al proveedor existente en el `409` `RFC_DUPLICADO` (backend, `openapi.yaml` y pruebas de TKT-029a).
