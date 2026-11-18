# TKT-012b · Mantenimiento y ciclo de vida de la obra

> Hub del ticket. Se lee **primero**, siempre.

## Estado

ARCHIVADO · las dos entregas (a: backend; b: pantalla y E2E) se fusionaron juntas en el PR #80. La planificación queda archivada. El PR se fusionó con una excepción aprobada por la persona dueña: la comprobación de dependencias estaba en rojo por avisos nuevos de `picomatch`, ajenos al ticket.

## Ficha

| | |
|---|---|
| **Tipo** | Funcionalidad |
| **Historia** | [[HDU-001]] — escenario 20 |
| **Épica / sprint** | HDU-001 · Obra y línea base, fase 1 |
| **Puntos** | Talla S en el backlog (TKT-012); con la pantalla, el diseño la parte en entregas |
| **Reglas implicadas** | `RN-01`, `RN-25`, `PA-02`, `PA-05`, `PA-18` |
| **Invariantes en riesgo** | Transición `PLANEACION` → `ACTIVA` del congelado (`PA-T17.8`), restricciones de `0006`, invariante 14, alta y lista de TKT-012a |
| **Módulos en alcance** | `presupuesto`; `auditoria` e `identidad` por su interfaz |
| **Capas en alcance** | dominio · aplicación · api · infraestructura · frontend. Migración posible si D-4 añade el verbo de bitácora |
| **Criterios `[M]`** | `CA-1` a `CA-18`, `CA-R1` a `CA-R5` |
| **Depende de** | TKT-012a (ARCHIVADO) |
| **Rama** | `tkt-012b-mantenimiento-obras` (sale de `Produccion`) |

## Artefactos

| Artefacto | Enlace | Comando | Estado |
|---|---|---|---|
| Spec | [spec.md](spec.md) | `/sdd-definir` | Escrita el 2026-11-17 |
| Design | [design.md](design.md) | `/sdd-disenar` | Escrito y aprobado el 2026-11-17 |
| Impl | [impl.md](impl.md) | `/sdd-ejecutar` | Escrito el 2026-11-17 |
| Delta | [delta.md](delta.md) | `/sdd-completar` | Escrito el 2026-11-17 |
| PR | [#80](https://github.com/FranciscoRodSilva/IA4Devs-Proyecto-Final/pull/80) | `/sdd-completar` | Fusionado el 2026-11-17 |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-11-17 | — | `SPEC PENDIENTE` | `/sdd-definir` | Spec creada tras la prueba manual de la entrega 3, que mostró que «Obras» solo permite crear. Must validado por la persona dueña: las cinco operaciones del borrador (editar, eliminar, suspender, reactivar, cerrar) con su máquina de estados, **más** la pantalla y una prueba de extremo a extremo. 18 criterios `[M]` y 5 de regresión; rechazos de forma, estado, historial, carrera con el congelado, motivo, rol y obra inexistente. Cinco huecos de regla abiertos (D-1 a D-5) con recomendación. INVEST: un fallo (tamaño), con partición en entregas a (backend) y b (pantalla y E2E) en un solo PR. La pasada adversarial la hizo quien redactó, no la skill |
| 2026-11-17 | `SPEC PENDIENTE` (hub en «SPEC LISTA PARA DISEÑO») | `DISEÑO PENDIENTE REVISIÓN` | `/sdd-disenar` | Diseño en dos entregas, un solo PR: **a** backend (A1 a A9: migración `0017` con `ELIMINAR`, dominio puro del ciclo de vida y del historial, repositorio, puerto de historial inyectado, casos de uso, API, contrato y concurrencia) y **b** pantalla y E2E (B1 a B6). Cubre `CA-1` a `CA-18` y `CA-R1` a `CA-R5` con 81 casos de prueba y 13 mutantes. `revisor-impacto`: fronteras no cruzadas y once hallazgos incorporados. `abogado-del-diablo`: siete objeciones, tres altas, incorporadas. Siete decisiones del diseño esperan a la persona dueña (D-DIS-1 a D-DIS-7); la spec se corrige con su respuesta (`CA-7`, `CA-8`, `CA-14`, `CA-18`). Aviso: el hub declaraba un estado distinto del que exige el gate del comando; se diseñó por instrucción expresa de la sesión que lo pidió |
| 2026-11-17 | `LISTO PARA EJECUTAR` | `EN REVISIÓN` | `/sdd-ejecutar` | Entregas a (A1–A9) y b (B1–B6) ejecutadas con TDD en una sola rama. Suite del backend `4184 passed, 26 skipped`; Vitest `625 passed`; E2E de humo `8 passed`; 23 mutantes de A9 muertos. `auditor-sql`: un hallazgo menor (índices por `obra_id`), declarado como deuda. `auditor-arquitectura`: F001 (fuente de historial de `archivos`) y F002a (cita de `RN-25` en la bitácora) corregidos por orden de la persona dueña y reauditados `APROBADO`; quedan abiertos F002b, F003, F004 y F005. Nada commiteado: el commit y el PR son de `/sdd-completar` |
| 2026-11-17 | `EN REVISIÓN` | `LISTO PARA PR` | `/sdd-revisar` | Revisión de las entregas a y b: suite del backend `4206 passed, 26 skipped`, Vitest `625 passed`, linters y `tipos:verificar` limpios. Dos ciclos de corrección: el primero aplicó `auditor-arquitectura F001` (fuente de historial de `archivos`) y `F002a` (cita de `RN-25`); el segundo, `auditor-seguridad F001` (el `409` por clave foránea ya no publica el nombre de la restricción), `auditor-codigo F001` a `F006` y `F008`, y tres Mayores de `auditor-docs` (`llms.txt`, `docs/05`, `spec.md` CA-16). Cinco auditores en `APROBADO`; `auditor-sql` con la condición de formalizar la deuda de índices en `delta.md`. El PR toca `docs/api/openapi.yaml`: señalarlo. Diferido por la persona dueña: F007 y observaciones. El E2E se repitió tras el ciclo 2: `8 passed` |
| 2026-11-17 | `LISTO PARA PR` | `PENDIENTE FUSIÓN` | `/sdd-completar` | Delta escrito (`auditor-docs` en `APROBADO` tras corregir un Mayor y cuatro Menores del propio delta), seis observaciones de proceso en `_evolucion.md` con la revisión de `meta-sdd` (seis propuestas sin aplicar), deuda de índices declarada con su alcance completo. Se abre el único PR del ticket |
| 2026-11-17 | `PENDIENTE FUSIÓN` | `ARCHIVADO` | `/sdd-completar TKT-012b` | PR #80 fusionado en `Produccion` (commit `03e2135`) con nueve de las diez comprobaciones requeridas en verde sobre `cb068b5`; la de «Dependencias · auditoría de vulnerabilidades» estaba en rojo por avisos nuevos de `picomatch` sin versión parcheada, ajenos al PR, y la persona dueña aprobó fusionar con esa excepción (fusión manual y sin `--admin`, porque `Produccion` no tiene protección de rama). La planificación queda archivada; el número del PR consta en el comentario de registro |
| 2026-11-17 | `DISEÑO PENDIENTE REVISIÓN` | `LISTO PARA EJECUTAR` | `/sdd-disenar` | La persona dueña aprobó el diseño completo en la conversación principal: todas las recomendaciones de D-DIS-1 a D-DIS-7 |

## Decisiones registradas

- 2026-11-17 · La persona dueña resolvió D-1 a D-5: historial **amplio** (línea base no vacía, importación, presupuesto de control o filas de módulos posteriores); transiciones `ACTIVA ↔ SUSPENDIDA`, `ACTIVA → CERRADA`, `SUSPENDIDA → CERRADA` y `PLANEACION → CERRADA`, con `CERRADA` terminal y único estado que bloquea la edición; verbo nuevo `ELIMINAR` con migración y ADR; borrado físico.
- 2026-11-17 · La sesión que encargó el diseño comunicó que la persona dueña aprobó las recomendaciones D-DIS-1 a D-DIS-7: `PLANEACION` ofrece Editar, Eliminar y Cerrar; `CA-18` usa dos obras (M1 `ACTIVA`, M2 `PLANEACION` con historial); `CA-7` se lee como «el congelado gana y el borrado responde 409»; `CA-8` suma `PLANEACION → CERRADA`; `23001` se traduce a `OBRA_CON_HISTORIAL`; «historial» es «existe alguna fila de `linea_base`»; se amplía el filtro de `x-tickets` y se añade `fuentes_historial` a `montar_presupuesto`. El texto de la spec ya está corregido.
- 2026-11-17 · La persona dueña validó que TKT-012b incluya la pantalla además del backend, para que la entrega 3 muestre las operaciones desde la interfaz.

## Tickets futuros sugeridos

- Reabrir una obra `CERRADA` (hoy terminal).
- Reglas por módulo para una obra suspendida (Compras, Almacén): entran con el primer consumidor de cada módulo.
