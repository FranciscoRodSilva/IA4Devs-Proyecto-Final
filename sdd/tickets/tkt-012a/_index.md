# TKT-012a · Alta y consulta de obras

> Hub del ticket. Se lee **primero**, siempre.

## Estado

PENDIENTE FUSIÓN

## Ficha

| | |
|---|---|
| **Tipo** | Funcionalidad |
| **Historia** | [[HDU-001]] — escenarios 1, 2 y 3 |
| **Épica / sprint** | HDU-001 · Obra y línea base, fase 1 |
| **Puntos** | Talla S en el backlog; parte de TKT-012 partido en TKT-012a y TKT-012b |
| **Reglas implicadas** | `RN-25`, `PA-02`, `PA-05`, `PA-18`; `RN-01` solo como contexto |
| **Invariantes en riesgo** | Ninguno de los 39 protege `obra` directamente; regresión de `PA-T17.8` y de las restricciones de la migración `0006` |
| **Módulos en alcance** | `presupuesto`; `auditoria` e `identidad` por su interfaz |
| **Capas en alcance** | dominio · aplicación · api · infraestructura · frontend. Sin migración |
| **Criterios `[M]`** | `CA-1` a `CA-13`, `CA-R1` a `CA-R3` |
| **Depende de** | TKT-011b, TKT-010, TKT-017 y TKT-008 (todas ARCHIVADO) |
| **Rama** | `tkt-012a-alta-de-obras` |

## Artefactos

| Artefacto | Enlace | Comando | Estado |
|---|---|---|---|
| Spec | [spec.md](spec.md) | `/sdd-definir` | Escrita el 2026-11-10 |
| Design | [design.md](design.md) | `/sdd-disenar` | Escrito y aprobado el 2026-11-10 |
| Impl | [impl.md](impl.md) | `/sdd-ejecutar` | Entregas a y b escritas |
| Delta | [delta.md](delta.md) | `/sdd-completar` | Escrito el 2026-11-10 |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-11-10 | — | `SPEC PENDIENTE` | `/sdd-definir` | Spec creada. TKT-012 partido en TKT-012a y TKT-012b por el plazo de la tercera entrega. Must validado por la persona dueña: `crear_obra`, `listar_obras`, `obtener_obra` y su pantalla con prueba de extremo a extremo. 13 criterios `[M]` más tres de regresión; rechazos de código duplicado, forma, rango de porcentajes, permiso, sesión, parámetros de lista y obra inexistente. Cuatro objeciones adversariales incorporadas, entre ellas que el usuario de humo es `COMPRAS` y que el E2E debía usar código único por corrida. INVEST sin fallos |
| 2026-11-10 | `SPEC PENDIENTE` | `DISEÑO PENDIENTE REVISIÓN` | `/sdd-disenar` | Diseño escrito por `arquitecto-tecnico` (opus): rutas `crear_obra`, `listar_obras` y `obtener_obra` con el índice `uq_obra_codigo` como árbitro del duplicado y de la carrera, sin migración; rango de porcentajes en una función pura de dominio; frontend con `FormularioCatalogo` extendido. Filas A1 a A5 (backend, ~480 líneas) y B1 a B5 (frontend y E2E, ~410 líneas) en dos entregas, un solo PR. `revisor-impacto`: sin frontera cruzada (16 contratos en verde), diseño incompleto; cinco hallazgos incorporados (entre ellos que la prueba TC-B19 de TKT-017 se rompe por la etiqueta `presupuesto`). Pasada adversarial: nueve objeciones, la del plazo con recomendación de recorte. Siete decisiones esperan a la persona dueña (D-1 a D-7) |
| 2026-11-10 | `DISEÑO PENDIENTE REVISIÓN` | `LISTO PARA EJECUTAR` | persona dueña | Diseño aprobado con recorte: D-1 a D-6 con la recomendación y D-7 con la alternativa (la acción `VER_OBRA` cierra el formulario; sin ficha de obra, unas 840 líneas en total). Spec ajustada en `CA-11` al mensaje del servidor del `403` y a la acción de ver la obra. Siguiente: `/sdd-ejecutar TKT-012a` sobre la entrega a (filas A1 a A5) |
| 2026-11-10 | `LISTO PARA EJECUTAR` | `EN REVISIÓN · entregas a y b` | `/sdd-ejecutar` | Entregas a (backend, A1 a A5) y b (frontend y extremo a extremo, B1 a B5) ejecutadas con TDD sobre la rama `tkt-012a-alta-de-obras`. Entrega a: suite de backend 2765 passed, siete mutantes caídos, `auditor-arquitectura` `APROBADO`. Entrega b: 255 pruebas de frontend y `npm run e2e` 5 passed; `auditor-seguridad` `APROBADO`; `auditor-arquitectura` y `auditor-codigo` con menores corregidos. Decisiones de la persona dueña durante la ejecución: renombrar la rama local previa, actualizar TC-86 de TKT-008c por la etiqueta «Ver la obra» y detener un Vite ajeno en el puerto 5173. Quedan para decidir F002 y F007 de `auditor-codigo` y cuatro huecos de la pantalla (ver `impl.md`). Siguiente: `/sdd-revisar TKT-012a` |
| 2026-11-10 | `EN REVISIÓN · entregas a y b` | `LISTO PARA PR` | `/sdd-revisar` | Revisión del ticket completo. Suite de backend 2767 passed y 26 omitidos, frontend 255 passed, E2E 5 passed, linters y `lint-imports` limpios. Auditorías: arquitectura y seguridad `APROBADO`; código y documentación `APROBADO CON MENORES RESUELTOS SIN REAUDITAR`. Decisiones de la persona dueña: ADR nuevo de la unicidad del código de obra (41 ADR) y F002 y F007 como deuda. Quedan comunicados N002, F011 y N008, y cuatro huecos de la pantalla. `docs/api/openapi.yaml` toca `maxLength` (D-5) y se señala a quien aprueba. Siguiente: `/sdd-completar TKT-012a` |
| 2026-11-10 | `LISTO PARA PR` | `PENDIENTE FUSIÓN` | `/sdd-completar` | Delta escrito, evolución registrada (`meta-sdd` propone siete cambios al toolkit, ninguno aplicado) y documentación auditada en tres ciclos. Decisiones de la persona dueña: el PR lleva `docs/05` completo y las carpetas de planificación de tkt-018a y tkt-029a, y el delta las declara. Se abre el único PR del ticket. Tras fusionar pasará a `ARCHIVADO` |

## Decisiones registradas

- **2026-11-10 · persona dueña.** Partir TKT-012 y dejar para TKT-012b `actualizar_obra`, `eliminar_obra`, `suspender_obra`, `reactivar_obra`, `cerrar_obra` y el esc. 20 de HDU-001, por el plazo del 12 de noviembre y porque sus huecos de reglas no están resueltos.
- **2026-11-10 · persona dueña.** Los porcentajes de retención (15) y de fondo de garantía (5) se precargan en el cliente como sugerencia editable; el servidor no tiene constante (`PA-02`). La interfaz muestra porcentaje y envía la fracción como cadena (`"0.150000"`).
- **2026-11-10 · persona dueña.** `tipo_contrato` lo envía el cliente, preseleccionado con su único valor, tal como lo define el borrador OpenAPI.
- **2026-11-10 · persona dueña.** Un porcentaje fuera de 0 a 1, o un umbral negativo, responde `422` `VALIDACION` por campo antes de llegar al motor.
- **2026-11-10 · persona dueña (aprobación del diseño).** D-1: el código de obra se recorta y se guarda en mayúsculas. D-2: los campos extra del cuerpo se ignoran. D-3: sección «Obras» en `/obras`, visible a los seis roles, con botón `+` solo para Director de Proyectos y Dirección General. D-4: lista por código ascendente con el identificador como desempate. D-5: `nombre` hasta 200 y `domicilio` hasta 500 caracteres, con `maxLength` en el borrador. D-6: el `403` muestra el mensaje del servidor. D-7: `VER_OBRA` cierra el formulario, sin ficha de obra.
- **2026-11-02 · persona dueña (`A9` de TKT-010).** La empresa de la obra es la única activa; `ObraNueva` no lleva `empresa_id`.

## Tickets futuros sugeridos

- **TKT-012b** · `actualizar_obra`, `eliminar_obra`, `suspender_obra`, `reactivar_obra` y `cerrar_obra`, con la máquina de estados de la obra. Resolver antes qué cuenta como «movimientos» en `OBRA_CON_HISTORIAL` y la acción de bitácora del borrado.
- **Selector de obra del armazón** (wireframe §2), que consume `listar_obras`.
- **Ficha de solo lectura de la obra** (`/obras/{id}`), destino natural de `VER_OBRA`.
- **`listar_tipos_partida` y `listar_insumos`**, con la captura de requisición y la previsualización de la importación.
