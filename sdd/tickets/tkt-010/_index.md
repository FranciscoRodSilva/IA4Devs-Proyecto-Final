# TKT-010 · Datos semilla con catálogos

> Hub del ticket. Se lee **primero**, siempre.

## Estado

TKT-010a: ARCHIVADO (al fusionarse su PR) · TKT-010b: LISTO PARA EJECUTAR. El paraguas TKT-010 se archiva cuando se archivan los dos hermanos

## Ficha

| | |
|---|---|
| **Tipo** | Fundación (asimilada a Funcionalidad sin criterios de negocio, como TKT-004) |
| **Historia** | Épica 0 · Fundación. Sin escenarios propios: HDU-001 esc. 10 y HDU-002 esc. 1 descansan en lo que siembra |
| **Épica / sprint** | Épica 0 · Sprint 2 |
| **Puntos** | Talla S |
| **Reglas implicadas** | Ninguna `RN-xx` se implementa. Dan sentido al catálogo `RN-02`, `RN-03`, `PA-01`, `RNF-07` |
| **Invariantes en riesgo** | 8, 21 y 27 del modelo de datos; `uq_tipo_partida_clave`, `uq_insumo_codigo` y `ck_usuario_email_minusculas`. Regresión: `CA-R1` a `CA-R7` |
| **Módulos en alcance** | `presupuesto` (`empresa`, `tipo_partida`, `insumo`, `precio_insumo`) e `identidad` (`usuario`, `usuario_rol`) |
| **Capas en alcance** | infraestructura (migración Alembic) y herramienta de operación. Sin dominio, aplicación, API ni frontend |
| **Depende de** | TKT-003 (ARCHIVADO), TKT-011a (ARCHIVADO, PR 31) y TKT-011b (ARCHIVADO, PR 32) |
| **Rama** | `tkt-010a-migracion-semilla` (TKT-010a, esta entrega) y `tkt-010b-herramienta-semilla-local` (TKT-010b) |

## Artefactos

| Artefacto | Enlace | Comando | Estado |
|---|---|---|---|
| Spec | [spec.md](spec.md) | `/sdd-definir` | Escrita el 2026-11-01 |
| Design | [design.md](design.md) | `/sdd-disenar` | Escrito el 2026-11-01 y aprobado el 2026-11-02 |
| Impl | [impl.md](impl.md) | `/sdd-ejecutar` | TKT-010a escrita el 2026-11-02; TKT-010b pendiente |
| Delta | [delta.md](delta.md) | `/sdd-completar` | TKT-010a escrito el 2026-11-02; TKT-010b añadirá el suyo |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-11-01 | — | `SPEC PENDIENTE` | `/sdd-definir` | Spec creada con el Must validado por la persona dueña |
| 2026-11-01 | `SPEC PENDIENTE` | `DISEÑO PENDIENTE REVISIÓN` | `/sdd-disenar` | Diseño escrito, impacto revisado sin frontera cruzada; espera aprobación y las preguntas P1 a P5 |
| 2026-11-02 | `DISEÑO PENDIENTE REVISIÓN` | `LISTO PARA EJECUTAR` | Persona dueña | Diseño aprobado con las decisiones P1 a P4 y la confirmación de A4 |
| 2026-11-02 | `LISTO PARA EJECUTAR` | `EN REVISIÓN` (solo TKT-010a) | `/sdd-ejecutar TKT-010a` | Filas A1 y A2 hechas, suite de 1698 en verde, cuatro mutantes caídos, `auditor-sql` y `auditor-arquitectura` aprobados. TKT-010b sigue `LISTO PARA EJECUTAR` |
| 2026-11-02 | `EN REVISIÓN` (solo TKT-010a) | `LISTO PARA PR` (solo TKT-010a) | `/sdd-revisar TKT-010a` | Suite de 1698 en verde reejecutada, linters limpios; `auditor-docs` pidió cambios (un Mayor y cuatro Menores), el corrector los aplicó y la reauditoría quedó `APROBADO` en el segundo ciclo. `auditor-arquitectura` y `auditor-sql` ya habían aprobado el código |
| 2026-11-02 | `LISTO PARA PR` (solo TKT-010a) | `ARCHIVADO` (solo TKT-010a, al fusionarse su PR) | `/sdd-completar TKT-010a` | Delta escrito, observaciones anotadas en `sdd/_evolucion.md`. El ticket queda archivado al fusionarse el PR; el número consta en el comentario de registro del PR |

## Decisiones registradas

Recortes de alcance aprobados, escalaciones resueltas, excepciones autorizadas. Cada una con fecha y quién decidió.

- 2026-11-01 · Persona dueña · Los 27 insumos son **sintéticos con forma real**, no los reales de Union Square: los presupuestos del cliente no se versionan (`RNF-07`, repositorio público). Mismo precedente que TKT-004.
- 2026-11-01 · Persona dueña · Reparto del mecanismo: la migración siembra `empresa` y `tipo_partida`; la herramienta, solo contra una base local, siembra los seis usuarios y los 27 insumos con sus precios. Corrige la primera decisión del mismo día, que ponía los insumos en la migración y los habría llevado a producción.
- 2026-11-01 · Persona dueña · Usuarios solo en local, contraseña desde el entorno. `PA-T13` (primer usuario en producción) sigue abierta y fuera de este ticket.
- 2026-11-01 · Persona dueña · Clave de insumo definida aquí `(asumido)`: código recortado y en mayúsculas. TKT-014 la hereda.
- 2026-11-01 · Persona dueña · RFC genérico público del SAT `(asumido)`; identificadores fijos; un conflicto deja la fila intacta; vigencia desde 2026-01-01 `(asumido)`; sin asiento en la bitácora; guarda de entorno por host local, sin ajuste nuevo.
- 2026-11-01 · Persona dueña · Valida el Must (M1 a M8).
- 2026-11-02 · Persona dueña · **P1:** el ticket se parte en dos hermanos con un PR cada uno y fusión a → b: **TKT-010a** (migración `0008`, fábrica y pruebas de la migración, filas A1 y A2) y **TKT-010b** (herramienta, documentación y ADR-032, filas B1 a B5). Ramas: `tkt-010a-migracion-semilla` y `tkt-010b-herramienta-semilla-local`.
- 2026-11-02 · Persona dueña · **P2:** plantilla de pruebas fiel a lo desplegado; la fábrica `DatosPresupuesto.tipo_partida` devuelve el tipo existente y `tester-backend` ajusta la precondición de tres pruebas de TKT-011 (estructura ca20, estructura ca01 con `empresa_con_obra` y regresión TC-18), sin cambiar lo que verifican. Se anota en `impl.md`.
- 2026-11-02 · Persona dueña · **P3:** `herramientas/` puede importar `ContrasenasArgon2` y `ConfiguracionIdentidad` desde el interior de `identidad`: es operación, no un módulo, y `import-linter` no la analiza.
- 2026-11-02 · Persona dueña · **P4:** se crea el ADR-032 y se actualiza `CLAUDE.md` (comando nuevo y conteo de ADR a 32, también en `README.md` y `llms.txt`).
- 2026-11-02 · Persona dueña · **A4 confirmado:** correos `<clave del rol en minúsculas>@cimenta.test` y una sola contraseña, `CIMENTA_SEMILLA_CONTRASENA`.
- 2026-11-02 · Persona dueña · Aprueba el diseño.

## Tickets futuros sugeridos

Lo que salió del alcance y merece su propio ticket.

- **Resolver `empresa_id` en el alta de obra (TKT-012).** `crear_obra` no recibe `empresa_id` y el borrador OpenAPI no menciona `empresa`; con una sola empresa sembrada, TKT-012 debe decidir cómo la obtiene (pregunta `A9` de la [spec](spec.md)). No se añadió a los criterios de TKT-012 en `docs/05-tickets-trabajo.md` porque eso amplía el alcance de otro ticket y lo decide la persona dueña: queda como entrada obligatoria de su `/sdd-definir`.
- **Regla de clave de insumo del importador (TKT-014).** Hoy solo está `(asumido)` en esta spec (`A2`). No se añadió a la ficha de TKT-014 por la misma razón: TKT-014 debe confirmarla o cambiarla en su `/sdd-definir`, antes de su propia spec.
- **Primer usuario en producción (`PA-T13`).** Sigue abierta; no es de este ticket.
- **Ajuste de entorno transversal** (`local`, `pruebas`, `demostracion`, `produccion`): hoy solo existe en la documentación. Haría innecesaria la guarda por host.
