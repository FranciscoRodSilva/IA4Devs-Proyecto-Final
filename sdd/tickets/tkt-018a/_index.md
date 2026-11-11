# TKT-018a · Pantalla de línea base y presupuesto de control

> Hub del ticket. Se lee **primero**, siempre.

## Estado

PENDIENTE FUSIÓN

## Ficha

| | |
|---|---|
| **Tipo** | Funcionalidad |
| **Historia** | [[HDU-001]] — escenarios 14, 15, 17, 18, 19, 22 y 23 |
| **Épica / sprint** | HDU-001 · Obra y línea base, fase 1 |
| **Puntos** | Talla M en el backlog; parte de TKT-018 partido en TKT-018a y TKT-018b |
| **Reglas implicadas** | `RN-01`, `RN-03`, `RN-04`, `PA-01`, `PA-03` |
| **Invariantes en riesgo** | Ninguno de backend; regresión de las pruebas compartidas de TKT-008 y TKT-012a y del contrato publicado |
| **Módulos en alcance** | Frontend: `modulos/presupuesto` y componentes compartidos. Sin módulo de backend |
| **Capas en alcance** | frontend. Sin backend ni migración (el script de semilla, *Should*, vive en `backend/herramientas`) |
| **Criterios `[M]`** | `CA-1` a `CA-13`, `CA-R1` y `CA-R2`; `CA-S1` es *Should* |
| **Depende de** | TKT-017 (ARCHIVADO) y TKT-012a (ARCHIVADO: fusionado en el PR #56) |
| **Rama** | `tkt-018a-pantalla-linea-base` (sale de `Produccion` después de integrar TKT-012a) |

## Artefactos

| Artefacto | Enlace | Comando | Estado |
|---|---|---|---|
| Spec | [spec.md](spec.md) | `/sdd-definir` | Escrita el 2026-11-10 |
| Design | [design.md](design.md) | `/sdd-disenar` | Escrito y aprobado el 2026-11-10 |
| Impl | [impl.md](impl.md) | `/sdd-ejecutar` | Entregas a, b y c escritas y revisadas |
| Delta | [delta.md](delta.md) | `/sdd-completar` | Escrito el 2026-11-11 |
| PR | Pendiente | `/sdd-completar` | Se abre tras este commit |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-11-10 | — | `SPEC PENDIENTE` | `/sdd-definir` | Spec creada. TKT-018 partido en TKT-018a (pantalla) y TKT-018b (importación) por el plazo de la tercera entrega. Must validado por la persona dueña: línea base, congelado con motivo y captura y recaptura del tope, con la obra de contexto en la ruta; solo frontend. 13 criterios `[M]` más dos de regresión y uno *Should*; rechazos de cada respuesta del servidor del congelado, tope superior a la venta, recaptura sin motivo o sin rol, importes mal formados y éxito parcial. Cinco objeciones adversariales incorporadas, entre ellas una cita de regla equivocada que se corrigió. Ocho preguntas abiertas con recomendación para el diseño. INVEST sin fallos, con reservas en tamaño y en orden de ejecución |
| 2026-11-10 | `SPEC PENDIENTE` | `DISEÑO PENDIENTE REVISIÓN` | `/sdd-disenar` | Diseño escrito por `arquitecto-tecnico` (opus): una sola pantalla en `/obras/:obraId/linea-base` con la línea base y el congelado arriba y el presupuesto de control abajo, sin backend ni tipos nuevos. Filas A1 a A5 (línea base y congelado, ~340 líneas), B1 a B4 (tope de control, ~340) y C1 y C2 (semilla local y E2E, ~140, recortable) en tres entregas y un solo PR. `revisor-impacto`: sin frontera cruzada (16 contratos en verde), diseño incompleto; sus hallazgos se incorporaron, entre ellos que el 403 muestre el mensaje del servidor como en TKT-012a y que la rama dependa de que `servidor.ts` ya traiga `obtener_obra`. Once decisiones esperan a la persona dueña (D-1 a D-11) |
| 2026-11-10 | `DISEÑO PENDIENTE REVISIÓN` | `LISTO PARA EJECUTAR` | persona dueña | Diseño aprobado con las recomendaciones de D-1 a D-11, incluida la entrega c (semilla local y E2E). Spec ajustada: el `403` muestra el mensaje del servidor. Siguiente: ejecutar después de integrar TKT-012a, con `/sdd-ejecutar TKT-018a` sobre la entrega a (filas A1 a A5) |
| 2026-11-11 | `LISTO PARA EJECUTAR` | `EN REVISIÓN · entrega a` | `/sdd-ejecutar` | Entrega a (filas A1 a A5) ejecutada con el ciclo TDD fila por fila en la rama `tkt-018a-pantalla-linea-base`, abierta desde `Produccion` tras TKT-012a. Suite de Vitest en verde (338 de 338), `eslint`, `tsc` y `tipos:verificar` limpios, tipos generados sin cambios. Doce mutantes, ninguno sobrevive. `auditor-arquitectura`: `APROBADO` en el primer ciclo, con cuatro observaciones que no bloquean. Un ajuste menor aprobado por la persona dueña (`DetalleCifras.tsx` trata `null` como vacío). Por excepción de sesión, todos los despachos corrieron en Fable 5.2 con esfuerzo medio. La documentación de wireframes queda para la fila B4. Siguiente: `/sdd-revisar TKT-018a` sobre la entrega a |
| 2026-11-11 | `EN REVISIÓN · entrega a` | `LISTO PARA EJECUTAR · entrega b` | `/sdd-revisar` | Entrega a revisada y acumulada en la rama del ticket, sin PR. Suite real: backend con 2767 pruebas en verde y 26 omitidas (`PA-T3`), 16 contratos de `import-linter`, Vitest 344 de 344, y `eslint`, `tsc`, `tipos:verificar` y `verificar_docs` limpios. `auditor-arquitectura` y `auditor-seguridad`: `APROBADO` en la primera pasada. `auditor-codigo`: `REQUIERE CAMBIOS` (un Mayor, `COD-1`: `formatearFecha` lanzaba ante una fecha inválida y dejaba la ruta en blanco; siete Menores) y `APROBADO` tras el ciclo 1. `auditor-docs`: `REQUIERE CAMBIOS` (dos Mayores, `DOC-1` y `DOC-2`: la documentación aplazada a B4 no enumeraba el wireframe §2b, §12 y §13) y `APROBADO` tras el ciclo 2. Dos ciclos de `corrector-revision` y seis pruebas nuevas. `DOC-7` no se aplicó por decisión del orquestador, porque pedía reformular salida literal, y el auditor lo retiró. Queda una pregunta para la persona dueña (`SEG-1`: los endpoints de línea base comprueban el rol y no una asignación por obra) y la documentación de wireframes sigue en la fila B4. Siguiente: `/sdd-ejecutar TKT-018a` sobre la entrega b |
| 2026-11-11 | `LISTO PARA EJECUTAR · entrega b` | `EN REVISIÓN · entrega b` | `/sdd-ejecutar` | Entrega b (filas B1 a B4) ejecutada con TDD fila por fila. Vitest 417 de 417, `eslint`, `tsc` y `tipos:verificar` limpios, generado sin cambios. Siete mutantes del diseño más variantes, ninguno sobrevive. `auditor-arquitectura`: `APROBADO` en el primer ciclo. B2 y B3 en `sonnet` por el disparador `RN-03`. Un archivo más que el diseño: `DetalleCifras.tsx` (un espacio). Documentación de wireframes hecha. Entrega c sin ejecutar. Siguiente: `/sdd-revisar TKT-018a` sobre la entrega b |
| 2026-11-11 | `EN REVISIÓN · entrega b` | `LISTO PARA EJECUTAR · entrega c` | `/sdd-revisar` | Entrega b revisada y acumulada en la rama del ticket, sin PR. Suite real: Vitest 438 de 438, `eslint`, `tsc`, `tipos:verificar` y `verificar_docs` limpios; el diff no toca backend ni contrato. `auditor-arquitectura` y `auditor-seguridad`: `APROBADO` en la primera pasada. `auditor-docs`: `REQUIERE CAMBIOS` (`DOC-1`) y corregido. `auditor-codigo`: `REQUIERE CAMBIOS` (tres Mayores, `COD-1` a `COD-3`: cola de confirmaciones, pruebas de la cola y confirmación de la recaptura con valores distintos de los del `409`) y dos ciclos de corrección con `corrector-revision` en `sonnet`; `F002` (segundo `PUT` concurrente en el diálogo) resuelto; `F003`, un Menor de pruebas, lo resolvió el orquestador sin tercera reauditoría y se comunica a la persona dueña. Veintiuna pruebas más que al cerrar la ejecución. Quedan dos preguntas para la persona dueña: `DOC-5` (ADR de `D-5`) y el marcador `(aprobado · D-7)` del wireframe. La entrega c sigue pendiente y su disparador de recorte no se cumplió. Siguiente: `/sdd-ejecutar TKT-018a` sobre la entrega c |
| 2026-11-11 | `LISTO PARA EJECUTAR · entrega c` | `EN REVISIÓN · entrega c` | `/sdd-ejecutar` | Entrega c (filas C1 y C2, *Should*) ejecutada con TDD fila por fila: semilla local de línea base `BORRADOR` y E2E del congelado y la captura de un tope. Backend: 2772 pruebas en verde y 26 omitidas (`PA-T3`), `ruff`, `mypy`, `lint-imports` (16 contratos) y `verificar_float` limpios. Frontend: Vitest 438 de 438 y Playwright 6 de 6. `auditor-arquitectura`: `APROBADO` en el primer ciclo, con dos observaciones. El rojo de C1 fue de módulo ausente y se repitió por comportamiento con un esqueleto no funcional creado por el orquestador, que además corrigió un import para respetar la interfaz publicada. Sin mutación: el diseño no la pide para la entrega c. Siguiente: `/sdd-revisar TKT-018a` sobre la entrega c |
| 2026-11-11 | `EN REVISIÓN · entrega c` | `LISTO PARA PR` | `/sdd-revisar` | Entrega c revisada, última del ticket: sin commit, lo hace `/sdd-completar`. Suite real: backend 2778 en verde y 26 omitidas (`PA-T3`), `ruff`, `mypy`, `lint-imports` y `verificar_float` limpios; Vitest 438 de 438; Playwright 6 de 6; `tipos:verificar` y `verificar_docs` limpios; sin cambios en `backend/cimenta`, contrato ni tipos generados. `auditor-arquitectura` y `auditor-seguridad`: `APROBADO` en la primera pasada. `auditor-docs` (`DOC-1` a `DOC-4`) y `auditor-codigo` (`COD-1` a `COD-3`): `REQUIERE CAMBIOS` y `APROBADO` tras un ciclo con `corrector-revision` en `haiku`, con las pruebas antes del código (seis pruebas nuevas de la semilla, `SEG-4` aplicada). Con la entrega c queda cumplido el ticket: `CA-1` a `CA-13`, `CA-R1`, `CA-R2` y `CA-S1`. Pendientes para la persona dueña: `DOC-5` (ADR de `D-5`), el marcador `(aprobado · D-7)` del wireframe, `F001` (la semilla crea la obra sin bitácora hasta que `crear_obra` esté en la interfaz) y `SEG-1` a `SEG-3` de la entrega c, previas a la entrega. Siguiente: `/sdd-completar TKT-018a` |
| 2026-11-11 | `LISTO PARA PR` | `PENDIENTE FUSIÓN` | `/sdd-completar` | Delta escrito y enlazado; `auditor-docs` del cierre: `REQUIERE CAMBIOS` (`DOC-1` Mayor, `DOC-2` y `DOC-3` Menores) y aplicados `DOC-2` a `DOC-5`; `DOC-1` lo resolvió la persona dueña (sin ADR para `D-5`). Registro de evolución y `meta-sdd` hechos: dos patrones nuevos y ocho decisiones propuestas, ninguna aplicada. Siguiente: commit, push y PR único del ticket |

## Decisiones registradas

- **2026-11-10 · persona dueña.** Partir TKT-018: TKT-018a sin importación, que necesita TKT-059 y pasa a TKT-018b.
- **2026-11-10 · persona dueña.** La captura y recaptura del presupuesto de control entra en TKT-018a, aunque ningún ticket la tenía como criterio; sin tope el hilo vertical no avanza.
- **2026-11-10 · persona dueña.** La obra de contexto va en la ruta (`/obras/:obraId/…`), con un enlace «Línea base» por obra en la lista de TKT-012a; sin selector de obra.
- **2026-11-10 · persona dueña (durante la ejecución).** Ajuste menor en la fila A2: `celda()` de `DetalleCifras.tsx` trata `null` como vacío, para que la tabla «Causas» no pinte el texto «null».
- **2026-11-10 · persona dueña (durante la ejecución).** Excepción de sesión: todos los agentes corren en Fable 5.2 con esfuerzo medio, sin cambiar el modelo declarado de cada agente.
- **2026-11-10 · persona dueña (aprobación del diseño).** D-1: la interfaz oculta el borrador a Compras. D-2: se muestra la línea base `CONGELADA` y, si no hay, el `BORRADOR` de mayor versión. D-3: el motivo del congelado va en línea. D-4: solo se muestra lo que trae el contrato. D-5: `PUT` secuencial por fila con éxito parcial. D-6: la rama sale de `Produccion` tras fusionar TKT-012a. D-7: las entradas de menú «Línea base» y «Presupuesto de control» muestran «elegir obra» sin tocar `secciones.ts`. D-8: el `403` muestra el mensaje del servidor. D-9: el E2E usa tres usuarios de humo. D-10: el cliente no pinta el aviso «mayor que la venta»: lo decide el `409` del servidor. D-11: las comas de millares se rechazan.
- **2026-11-11 · persona dueña (tras `/sdd-revisar` de la entrega a).** `SEG-1`: Director de Proyectos, Dirección General y Compras ven todas las obras por diseño. Los endpoints de línea base comprueban el rol y no una asignación de la persona a la obra, y así debe ser: no hace falta ticket de backend.
- **2026-11-11 · persona dueña (en `/sdd-completar`).** `D-5` no tendrá ADR: es una decisión de presentación del cliente, ya aprobada y justificada en el diseño y probada por el éxito parcial; escribirlo obligaría a actualizar los conteos de ADR de la documentación.

## Tickets futuros sugeridos

- **TKT-018b** · Flujo de importación completo (subida por `archivo`, análisis, previsualización, errores, confirmación) y la deuda de TKT-017 que va con él.
- **Tablas «Ver conceptos» y «Ver explosión por tipo de partida»** del boceto 4a, con su paginación.
- **Selector de obra del armazón** (wireframe §2).
- **Quién importó y cuándo, con los conteos de conceptos e insumos**, que el boceto 4a dibuja y el contrato no trae: exigiría ampliar `LineaBase` en el backend.
