# TKT-019 · Esquema y migraciones del módulo compras

> Hub del ticket. Se lee **primero**, siempre.

## Estado

PENDIENTE FUSIÓN

## Ficha

| | |
|---|---|
| **Tipo** | Funcionalidad (esquema) con una dependencia de seguridad incluida |
| **Historia** | [[HDU-002]] y sus vecinas HDU-003, HDU-004 y HDU-005, que habilita sin probar sus escenarios |
| **Épica / sprint** | HDU-002 · Requisición con control de presupuesto, fase 1 |
| **Puntos** | Talla S en el backlog; con siete tablas y el bump de `dnspython` es más probable M |
| **Reglas implicadas** | `RN-02`, `RN-03`, `RN-04`, `RN-06`, `RN-07` |
| **Invariantes en riesgo** | 1, 2, 8 y 9; regresión de la cadena de migraciones, del esquema anterior y del `uv.lock` |
| **Módulos en alcance** | `compras` (solo esquema) |
| **Capas en alcance** | infraestructura (esquema y migración `0014`) y la cadena de dependencias. Sin dominio, aplicación, api ni frontend |
| **Criterios `[M]`** | `CA-1` a `CA-13`, `CA-R1`, `CA-R2` y `CA-R3` |
| **Depende de** | TKT-011a (ARCHIVADO) |
| **Rama** | `tkt-019-esquema-compras` (una sola por ticket) |

## Artefactos

| Artefacto | Enlace | Comando | Estado |
|---|---|---|---|
| Spec | [spec.md](spec.md) | `/sdd-definir` | Escrita el 2026-11-14 |
| Design | [design.md](design.md) | `/sdd-disenar` | Escrito el 2026-11-14; aprobado el 2026-11-15 |
| Impl | [impl.md](impl.md) | `/sdd-ejecutar` | Escrita el 2026-11-15 |
| Delta | [delta.md](delta.md) | `/sdd-completar` | Escrito el 2026-11-15 |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-11-14 | — | `SPEC PENDIENTE` | `/sdd-definir` | Spec creada. Must validado por la persona dueña: siete tablas de `compras` con la migración `0014` y la subida de `dnspython` (`GHSA-vvf4-9x63-8xvv`), que se incluyó en este ticket por decisión de la persona dueña. 13 criterios `[M]` más tres de regresión; rechazos de centro de costos nulo, estados, cifras negativas, folio, solicitud sin motivo, excedente de lo ordenado, reprogramación sin motivo, privilegios y auditoría sin parche. Cinco objeciones adversariales acogidas. Catorce preguntas abiertas con recomendación para el diseño. INVEST sin fallos, con reservas en independencia y tamaño |
| 2026-11-14 | `SPEC PENDIENTE` | `DISEÑO PENDIENTE REVISIÓN` | `/sdd-disenar` | Diseño escrito por `arquitecto-tecnico` (opus): dos migraciones sobre `0013` (`0014` con las siete tablas, restricciones, índices, dos disparadores de borrado y permisos; `0015` con la semilla de folios), la subida de `dnspython` como fila aparte y la documentación. Sin Python en `cimenta/`. Cinco filas (F1 a F5), unas 330 líneas de producción y unas 1,000 de pruebas, en una sola entrega y un solo PR. `revisor-impacto`: sin frontera cruzada (16 contratos en verde); sus siete hallazgos se incorporaron. Pasada adversarial: doce objeciones, todas acogidas. Diecinueve decisiones esperan a la persona dueña (D-1 a D-19), la central es D-3 |
| 2026-11-15 | `DISEÑO PENDIENTE REVISIÓN` | `LISTO PARA EJECUTAR` | persona dueña | Diseño aprobado con las recomendaciones de las diecinueve decisiones (D-1 a D-19), sin cambios. El marcador `(provisional · D-n)` de `design.md` pasó a `(aprobada · D-n)` |
| 2026-11-15 | `LISTO PARA EJECUTAR` | `EN REVISIÓN` | `/sdd-ejecutar` | Cinco filas ejecutadas con TDD en la rama `tkt-019-esquema-compras`: `dnspython` 2.9.2 (el filtro de `pip-audit` sale con 0; no hace falta `CA-13`), migración `0014` con las siete tablas, disparadores `IN002` y privilegios, migración `0015` con la semilla de folios, y la documentación. Suite completa `3574 passed, 26 skipped`; las cuatro suites del ticket `175 passed`; mutación 19 de 19. `auditor-arquitectura` `APROBADO`; `auditor-sql` `REQUIERE CAMBIOS` con dos Menores: `F001` corregido (`LOCK TABLE` en las guardas de bajada) y `F002` (índice de `solicitud_autorizacion.obra_id`) queda como excepción declarada por contradecir D-7. Sin commit todavía |
| 2026-11-15 | `EN REVISIÓN` | `LISTO PARA PR` | `/sdd-revisar` | Revisión: suite completa `3574 passed, 26 skipped`, `ruff`, `mypy` y `lint-imports` limpios; 15 criterios `[M]` cumplidos (`CA-12` se cierra en el pipeline, `CA-13` no aplica). `auditor-arquitectura`, `auditor-sql` (reauditoría) y `auditor-seguridad` `APROBADO`; `auditor-docs` `APROBADO CON MENORES RESUELTOS SIN REAUDITAR` tras corregir dos Mayores (diagrama de `docs/02`, ADR de D-3, que la persona dueña decidió crear: conteo de ADR 43→44) y tres Menores; `F003` y `F006` los resolvió el orquestador. Sin commit todavía |
| 2026-11-15 | `LISTO PARA PR` | `PENDIENTE FUSIÓN` | `/sdd-completar` | Delta escrito y auditado por `auditor-docs` (dos Menores de redacción, resueltos por el orquestador con el texto literal del auditor); `_evolucion.md` actualizado con seis observaciones y `meta-sdd` propone seis mejoras sin aplicar. Siguiente: `code-review`, commit, PR y comprobaciones |

## Decisiones registradas

- **2026-11-15 · persona dueña.** Crear el ADR de D-3 (`20261115-disparadores-de-borrado-en-compras.md`) a petición de `auditor-docs`, aunque el diseño decía «sin ADR»; el conteo de ADR pasa de 43 a 44.
- **2026-11-15 · persona dueña.** El hallazgo `F002` de `auditor-sql` (índice sobre `solicitud_autorizacion.obra_id`) queda como excepción declarada: se mantiene el D-7 aprobado y el ticket de la bandeja (HDU-003) añade el índice con `EXPLAIN`.
- **2026-11-15 · persona dueña.** Aprobadas todas las decisiones del diseño, D-1 a D-19, con la recomendación de cada una. En D-3 rige la opción B (dos disparadores con `IN002`); en D-6 y D-13 rige lo que el diseño recomienda frente a la spec; en D-8 la cabeza queda en `0015`; en D-15 el folio es nulable solo en `BORRADOR`; en D-19 el comentario de `ci.yml` se firma como «la persona dueña del proyecto» con revisión el 2026-12-14.
- **2026-11-14 · persona dueña.** Incluir la subida de `dnspython` en TKT-019 (el ticket de esquema), en lugar de un ticket aparte.
- **2026-11-14 · persona dueña.** Must validado: las siete tablas de `compras` y la subida de `dnspython`; los índices de rendimiento de §15 quedan como pregunta abierta para el diseño.
- **2026-11-14 · persona dueña.** Si no existe una versión corregida de `dnspython`, el aviso se ignora con `--ignore-vuln` fechado y firmado por la persona dueña.
- **2026-11-14 · persona dueña.** `importe_disponible` y `cantidad_disponible` quedan exentos del `CHECK >= 0` del invariante 8.
- **2026-11-14 · persona dueña.** El estado de la orden de compra no se guarda: solo se persiste la cancelación.

## Tickets futuros sugeridos

- En el ticket de la bandeja de pendientes (HDU-003), añadir el índice `(obra_id, estado)` sobre `solicitud_autorizacion`, comprobado con `EXPLAIN` (excepción `F002` de `auditor-sql`, aceptada el 2026-11-15).

- Actualizar `docs/03-modelo-datos.md` para reconciliar el diagrama de `orden_compra` con la decisión de no guardar su estado, dentro de este mismo ticket (no es un ticket aparte).
- Una vez fusionado, los 10 avisos de Dependabot del repositorio (1 alto y los demás medios) merecen su propia revisión: no son de este ticket.
