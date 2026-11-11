# TKT-029a · Catálogo de proveedores, sin baja

> Hub del ticket. Se lee **primero**, siempre.

## Estado

LISTO PARA EJECUTAR

## Ficha

| | |
|---|---|
| **Tipo** | Funcionalidad |
| **Historia** | [[HDU-004]] — escenarios 2, 3 y la mitad de desactivación del 12 |
| **Épica / sprint** | HDU-004 · Orden de compra a proveedor, fase 1 (el catálogo se adelanta por el plazo de la tercera entrega) |
| **Puntos** | Talla S en el backlog; parte de TKT-029 partido en TKT-029a y TKT-029b |
| **Reglas implicadas** | `RN-17`; `RN-15` y `RN-16` solo como contexto (v1.1) |
| **Invariantes en riesgo** | 28, 8 y 10; regresión de la cadena de migraciones y de las rutas protegidas |
| **Módulos en alcance** | `proveedores`; `auditoria` e `identidad` por su interfaz |
| **Capas en alcance** | dominio · aplicación · api · infraestructura. Con migración `0012`. Sin frontend |
| **Criterios `[M]`** | `CA-1` a `CA-11`, `CA-R1` y `CA-R2` |
| **Depende de** | TKT-003, TKT-005, TKT-006 y TKT-007 (todas ARCHIVADO) |
| **Rama** | `tkt-029a-catalogo-proveedores` |

## Artefactos

| Artefacto | Enlace | Comando | Estado |
|---|---|---|---|
| Spec | [spec.md](spec.md) | `/sdd-definir` | Escrita el 2026-11-10 |
| Design | [design.md](design.md) | `/sdd-disenar` | Escrito y aprobado el 2026-11-10 |
| Impl | `impl.md` (se enlaza en `/sdd-ejecutar`) | `/sdd-ejecutar` | Pendiente |
| Delta | `delta.md` (se enlaza en `/sdd-completar`) | `/sdd-completar` | Pendiente |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-11-10 | — | `SPEC PENDIENTE` | `/sdd-definir` | Spec creada. TKT-029 partido en TKT-029a y TKT-029b por el plazo de la tercera entrega. Must validado por la persona dueña: esquema `proveedor` y las cinco operaciones de catálogo y desactivación, solo backend, sin baja ni puerto ni pantalla. 11 criterios `[M]` más dos de regresión; rechazos de RFC duplicado (también en carrera), forma, permiso, listado, consulta, cambio y desactivación. Cuatro objeciones adversariales incorporadas. Seis preguntas abiertas con recomendación para el diseño y un hallazgo sobre el wireframe. INVEST sin fallos, con reserva en el tamaño |
| 2026-11-10 | `SPEC PENDIENTE` | `DISEÑO PENDIENTE REVISIÓN` | `/sdd-disenar` | Diseño escrito por `arquitecto-tecnico` (opus): patrón de TKT-017 y TKT-012a, sin baja ni puerto ni pantalla; el índice `uq_proveedor_rfc` arbitra el duplicado y la carrera; `REVOKE DELETE` al rol de aplicación; copia local de `MetaPagina` y `Motivo` en `proveedores`, sin paquete nuevo ni ADR. Filas A1 a A4 (esquema, dominio, repositorio y casos de uso, ~480 líneas) y B1 y B2 (API, borrador y tipos, ~290 líneas) en dos entregas y un solo PR. `revisor-impacto`: sin frontera cruzada (16 contratos en verde), diseño incompleto; sus hallazgos se incorporaron, entre ellos que la premisa del paquete `contrato_api` era falsa (Pydantic fusiona clases idénticas) y que la migración `0012` afecta a las suites que bajan desde la cabeza. Nueve decisiones esperan a la persona dueña (D-1 a D-9) |
| 2026-11-10 | `DISEÑO PENDIENTE REVISIÓN` | `LISTO PARA EJECUTAR` | persona dueña | Diseño aprobado con las recomendaciones de D-1 a D-9 (ver «Decisiones registradas»). Siguiente: `/sdd-ejecutar TKT-029a` sobre la entrega a (filas A1 a A4) |

## Decisiones registradas

- **2026-11-10 · persona dueña.** Partir TKT-029: TKT-029a sin la baja protegida (`dar_baja_proveedor`, `PROVEEDOR_CON_ORDENES_ABIERTAS`), que necesita órdenes de compra y queda para TKT-029b tras TKT-019.
- **2026-11-10 · persona dueña.** El puerto `CatalogoProveedores` se difiere a TKT-030, su primer consumidor.
- **2026-11-10 · persona dueña.** La pantalla del catálogo no entra: es de TKT-032.
- **2026-11-10 · persona dueña (aprobación del diseño).** D-1: el RFC se recorta de espacios y se pasa a mayúsculas. D-2: el `409` `RFC_DUPLICADO` lleva `proveedor_existente_id` y «nombre · RFC», sin acción. D-3: el `PATCH` se admite sobre un proveedor `DESACTIVADO`. D-4: se quita `DELETE` al rol de aplicación sobre `proveedor`. D-5: `nombre` hasta 200 caracteres, con `maxLength` en el borrador. D-6: los campos extra del cuerpo se ignoran. D-7: copia local de `MetaPagina` y `Motivo` en `proveedores`, sin paquete nuevo ni ADR. D-8: lista por nombre y después por identificador. D-9: `q` hasta 200 caracteres y sin `NUL`.

## Tickets futuros sugeridos

- **TKT-029b** · `dar_baja_proveedor` con su rechazo por órdenes abiertas y la prueba con orden `PARCIAL` sembrada, más el puerto `CatalogoProveedores`. Resolver antes el verbo de bitácora de la baja y la máquina de estados del proveedor (reactivación, baja desde `DESACTIVADO`).
- **Reconciliar `docs/08-wireframes.md`** con el borrador sobre la baja del proveedor, con TKT-032.
- **Pantalla del catálogo de proveedores** (TKT-032), que necesita el desplegable de `FormularioCatalogo` de TKT-012a.
