# TKT-011 · Esquema y migraciones del módulo presupuesto

> Hub del ticket. Se lee **primero**, siempre.

## Estado

ARCHIVADO (al fusionarse el PR de la entrega TKT-011b; la entrega TKT-011a ya se fusionó, PR 31)

## Ficha

| | |
|---|---|
| **Tipo** | Funcionalidad (en la práctica, esquema) |
| **Historia** | [[HDU-001]] — sin escenarios propios: los escenarios 3, 8, 9, 18, 19 y 27 dependen de garantías que nacen aquí y los implementan TKT-012 a TKT-018 |
| **Épica / sprint** | Sprint 2 · primer ticket de HDU-001 |
| **Puntos** | Talla M en el ticket; partido en TKT-011a y TKT-011b (ver «Partición propuesta» en [design.md](design.md)) |
| **Reglas implicadas** | Ninguna `RN-xx` se implementa. Dan la base física a `RN-01`, `RN-02`, `RN-03`, `RN-24` y `RN-25`; `RNF-09` y `RNF-17` fijan privilegios y latido |
| **Invariantes en riesgo** | 5, 6, 8, 13, 14, 19 y 27 del modelo de datos. Regresión: 10, 20 y 21, la cadena de migraciones, la regla 3 (fronteras) y la regla 1 (dinero) — `CA-R1` a `CA-R6` |
| **Módulos en alcance** | `presupuesto` |
| **Capas en alcance** | infraestructura (migración Alembic) y pruebas de esquema. Sin dominio, aplicación, API ni frontend |
| **Depende de** | TKT-003 (ARCHIVADO). El corte de TKT-059 lo decidió la persona dueña el 2026-11-01 |
| **Rama** | `tkt-011b-linea-base-importacion-permisos` (TKT-011b, esta entrega); `tkt-011a-esquema-estructura-catalogos` (TKT-011a, ya fusionada) |

## Artefactos

| Artefacto | Enlace | Comando | Estado |
|---|---|---|---|
| Spec | [spec.md](spec.md) | `/sdd-definir` | Escrita el 2026-11-01 |
| Design | [design.md](design.md) | `/sdd-disenar` | Escrito y aprobado el 2026-11-01 |
| Impl | [impl.md](impl.md) | `/sdd-ejecutar` | Entregas TKT-011a y TKT-011b escritas el 2026-11-01 |
| Delta | [delta.md](delta.md) | `/sdd-completar` | Escrito el 2026-11-01 (entregas TKT-011a y TKT-011b) |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-11-01 | — | `SPEC PENDIENTE` | `/sdd-definir` | Spec creada. Must validado por la persona dueña: M1 a M7 más M8, consecuencia documental, con `M5` ampliado tras la pasada adversarial. 20 criterios `[M]`, uno `[S]` y seis de regresión, con rechazo en cada garantía. INVEST con dos reservas (talla y granularidad). Escalaciones resueltas durante la definición: fase 2 (`rendimiento_observado`, `dias_semana_laboral`) y huecos de inmutabilidad |
| 2026-11-01 | `SPEC PENDIENTE` | `DISEÑO PENDIENTE REVISIÓN` | `/sdd-disenar` | Diseño escrito por `arquitecto-tecnico` (opus). Condición de parada 3: ~2,175 líneas, se propone partir en TKT-011a (`0006`) y TKT-011b (`0007`). `revisor-impacto`: sin frontera cruzada, seis hallazgos incorporados. `abogado-del-diablo`: cinco objeciones, la más seria sobre la clase del `SQLSTATE` `CM001`. Diez preguntas (P1 a P10) esperan a la persona dueña; trece experimentos quedan `(sin ejecutar)` hasta la fila A0 |
| 2026-11-01 | `DISEÑO PENDIENTE REVISIÓN` | `LISTO PARA EJECUTAR` | persona dueña | Diseño aprobado con las recomendaciones del arquitecto en P1 a P10. Spec ajustada en el mismo acto (contexto, CA-1, CA-8, CA-18, CA-19, CA-R4, DoD) |
| 2026-11-01 | `LISTO PARA EJECUTAR` | `EN REVISIÓN` | `/sdd-ejecutar` | Entrega TKT-011a ejecutada (filas A0 a A7, migración `0006`, rama `tkt-011a-esquema-estructura-catalogos`): 125 pruebas nuevas, suite completa 1528 en verde, seis mutantes de cierre y diecinueve de A5 detectados. `auditor-sql` APROBADO; `auditor-arquitectura` con dos menores ya resueltos. TKT-011b queda por ejecutar y exige antes la decisión sobre la clase del `SQLSTATE` |
| 2026-11-01 | `EN REVISIÓN` | `LISTO PARA PR` | `/sdd-revisar` | Entrega TKT-011a revisada: 2 ciclos de corrección de código y 2 de documentación más una tercera pasada acotada; `auditor-arquitectura`, `auditor-sql`, `auditor-codigo` y `auditor-docs` en `APROBADO`; suite completa 1528 en verde; sin hallazgos críticos ni mayores pendientes. `lychee` 0.24.2 instalado en local y sin errores sobre la documentación. TKT-011b sigue sin ejecutar |
| 2026-11-01 | `LISTO PARA PR` | `ARCHIVADO` | `/sdd-completar` | Entrega TKT-011a: delta escrito, auditoría de documentación atendida y observaciones de proceso anotadas en `sdd/_evolucion.md`. La entrega queda archivada al fusionarse su pull request; el número consta en el comentario de registro del PR. El ticket paraguas TKT-011 sigue abierto hasta ejecutar TKT-011b |
| 2026-11-01 | `ARCHIVADO` (entrega a) | `LISTO PARA EJECUTAR` (entrega b) | persona dueña | La persona dueña pidió ejecutar TKT-011b. El diseño de las dos entregas lo aprobó en el gate del 2026-11-01 y la dependencia, TKT-011a, está fusionada (PR 31, merge `f334b97`). La rama de esta entrega es `tkt-011b-linea-base-importacion-permisos` |
| 2026-11-01 | `LISTO PARA EJECUTAR` (entrega b) | `EN REVISIÓN` (entrega b) | `/sdd-ejecutar` | Entrega TKT-011b ejecutada (filas B1 a B8, migración `0007`, rama `tkt-011b-linea-base-importacion-permisos`): 160 casos de prueba nuevos, suite completa 1688 en verde, quince mutantes de cierre y los de la guarda detectados. Auditorías de arquitectura y SQL con Menores atendidos en un ciclo de corrección. Decisión de la persona dueña: la bajada de `0007` se niega con una línea base `CONGELADA` o `SUPERSEDIDA` |
| 2026-11-01 | `EN REVISIÓN` (entrega b) | `LISTO PARA PR` (entrega b) | `/sdd-revisar` | Entrega TKT-011b revisada: `auditor-arquitectura` y `auditor-sql` reauditados en `APROBADO`; `auditor-codigo` con ocho Menores corregidos y reauditado en `APROBADO`; `auditor-docs` con cuatro Menores y seis observaciones en la primera pasada y dos Menores de redacción en la segunda, resueltos por el orquestador con el texto literal del auditor. Suite completa `1688 passed`. Quedan como deuda declarada: la edición de `.claude/agents/auditor-arquitectura.md` (sin aprobación de la persona dueña), el procedimiento de retiro de una línea base y la pregunta `PA-T17` de TKT-017 |
| 2026-11-01 | `LISTO PARA PR` (entrega b) | `ARCHIVADO` | `/sdd-completar` | Entrega TKT-011b: delta escrito, observaciones de proceso anotadas en `sdd/_evolucion.md` y revisadas por `meta-sdd`, auditoría de documentación de cierre atendida. Con las dos entregas, el ticket TKT-011 queda archivado al fusionarse el pull request de la entrega b; el número consta en el comentario de registro del PR |

## Decisiones registradas

- 2026-11-01 · **Gate del diseño.** La persona dueña aprobó el diseño con las recomendaciones del arquitecto a las preguntas P1 a P10. Se parte el ticket en TKT-011a (`0006`) y TKT-011b (`0007`), con un PR cada uno que se fusiona en ese orden. Los conjuntos cerrados se declaran con `CHECK` con nombre en lugar de `ENUM` (ADR-030). Se ajustan TC-12 y TC-13 de TKT-057 en la fila A1. El rechazo del invariante 14 responde con un `SQLSTATE` propio, `CM001`, salvo que la fila A0 compruebe que su clase cae en el rango que el estándar reserva y haya que elegir otra (ADR-031, pendiente: lo escribe TKT-011b en la fila B7). Se confirman la tabla de nulabilidad y los rangos de `PA-T5`. Se adoptan `FOR SHARE` y un `UPDATE` que congela; el nombre abreviado de la unicidad de la explosión queda como `(asumido)`. Se generaliza la expresión regular del conteo de ADR en `tools/tests/test_definicion_revision.py`, y se editan `CLAUDE.md`, `README.md` y `llms.txt`; los textos de `.claude/` quedan para TKT-011b (P10). Se añaden los mutantes MB-13 a MB-15. Decidió la persona dueña.
- 2026-11-01 · **Medición de `E-13`.** Pasó de B8 a B2 (objeción 11 de la pasada independiente) y dio `total 0.070 s` frente al límite de 15 s.
- 2026-11-01 · **Guarda de la bajada de `0007`.** Se niega con una línea base `CONGELADA` o `SUPERSEDIDA`, no solo con `CONGELADA` (CA-19 ampliado), y toma `LOCK TABLE linea_base IN ACCESS EXCLUSIVE MODE` antes de comprobar. El procedimiento para retirar una línea base queda sin definir y lo decide la persona dueña fuera de la migración. Decidió la persona dueña.
- 2026-11-01 · **`SQLSTATE` del disparador de TKT-011b.** `IN001` (clase `IN`, de «inmutable»), en lugar de `CM001`, porque la experiencia de la fila A0 confirmó que la clase `CM` cae en el rango que el estándar SQL reserva. `design.md` actualizado. Decidió la persona dueña.

- 2026-11-01 · **Fase.** `rendimiento_observado` se crea vacía y sin escritor, aunque el PRD §7 pone su cálculo en la v1.1; `empresa.dias_semana_laboral` se crea en este ticket porque el módulo `personal` no puede alterar una tabla de `presupuesto`. Decidió la persona dueña.
- 2026-11-01 · **Restricciones del modelo que quedan fuera.** `UNIQUE (apu.concepto_id)`, `UNIQUE (linea_base.obra_id, version)`, el `CHECK` de congelado de `linea_base` y la coherencia de `concepto.obra_id` con su jerarquía. Solo `obra.codigo` único entra como Must. Decidió la persona dueña.
- 2026-11-01 · **ORM.** Solo migración y pruebas de esquema; sin modelos ni repositorios. Decidió la persona dueña.
- 2026-11-01 · **Invariante 8 ampliado** a toda cantidad, precio, importe y rendimiento; **auditoría** solo donde el modelo o el borrador la usan; y los valores por omisión del diseño (`PA-T6`, `PA-T8`, `PA-T9`, `PA-T12`). Decidió la persona dueña.
- 2026-11-01 · **Inmutabilidad ampliada.** El disparador cubre también `INSERT` en las copias y la fila `linea_base` solo avanza `BORRADOR` → `CONGELADA` → `SUPERSEDIDA`. Decidió la persona dueña tras la pasada adversarial.

## Tickets futuros sugeridos

- **Protección de base de las cuatro restricciones que quedan fuera:** `UNIQUE (apu.concepto_id)`, `UNIQUE (linea_base.obra_id, version)`, el `CHECK` de que una `CONGELADA` lleve `congelada_en` y `congelada_por_id`, y la coherencia de `concepto.obra_id` con la jerarquía. Hasta entonces las protegen los casos de uso de TKT-013 a TKT-017.
- **Quitar `dias_semana_laboral` de los criterios de TKT-049**, que solo la consume (`PA-T2`).
- **Modelos ORM y repositorios de `presupuesto`:** cada ticket los añade con el primer caso de uso que los usa (TKT-012 abre con `obra` y `empresa`).
