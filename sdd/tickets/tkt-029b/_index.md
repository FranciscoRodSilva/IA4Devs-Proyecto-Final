# TKT-029b · Baja protegida de proveedores

> Hub del ticket. Se lee **primero**, siempre.

## Estado

PENDIENTE FUSIÓN

## Ficha

| | |
|---|---|
| **Tipo** | Funcionalidad |
| **Historia** | [[HDU-004]] escenario 12 completo (TKT-029a cubrió su mitad de desactivación) |
| **Épica / sprint** | HDU-004 · Proveedores y órdenes de compra, fase 1 |
| **Puntos** | Talla S en el backlog (mitad de TKT-029); con la migración `0016` y la primera función de `compras` es más probable S alta |
| **Reglas implicadas** | Ninguna `RN-xx` propia; `RN-06` como contexto. El rechazo es `CONFLICTO` |
| **Invariantes en riesgo** | 28 y 10; en la siembra, 8 y 2. Regresión de la cadena de migraciones, de la frontera entre módulos y de TKT-029a |
| **Módulos en alcance** | `proveedores` y `compras` (solo su interfaz de lectura), más `auditoria` por su interfaz |
| **Capas en alcance** | dominio, aplicación, api e infraestructura. Con migración `0016`. Sin frontend |
| **Criterios `[M]`** | `CA-1` a `CA-14`, `CA-R1` a `CA-R4` |
| **Depende de** | TKT-029a (ARCHIVADO), TKT-019 (ARCHIVADO) |
| **Rama** | `tkt-029b-baja-proveedores` (una sola por ticket, también si está partido en entregas) |

## Artefactos

| Artefacto | Enlace | Comando | Estado |
|---|---|---|---|
| Spec | [spec.md](spec.md) | `/sdd-definir` | Escrita el 2026-11-15 |
| Design | [design.md](design.md) | `/sdd-disenar` | Escrito el 2026-11-15; aprobado el 2026-11-15 |
| Impl | [impl.md](impl.md) | `/sdd-ejecutar` | Entregas a y b escritas el 2026-11-15 y el 2026-11-16 |
| Delta | [delta.md](delta.md) | `/sdd-completar` | Escrito el 2026-11-16 |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-11-15 | — | `SPEC PENDIENTE` | `/sdd-definir` | Spec creada. Must validado por la persona dueña: `POST /baja` con motivo desde `ACTIVO` o `DESACTIVADO`, rechazo `PROVEEDOR_CON_ORDENES_ABIERTAS`, verbo `DAR_BAJA` con migración `0016`, función mínima de órdenes pendientes en `compras.interfaz` y prueba con una orden `PARCIAL` sembrada. 14 criterios `[M]` más cuatro de regresión; diez rechazos o escenarios de rechazo. Cinco objeciones adversariales acogidas. Diez supuestos o preguntas abiertas, tres con recomendación para el diseño |

| 2026-11-15 | `SPEC PENDIENTE` | `DISEÑO PENDIENTE REVISIÓN` | `/sdd-disenar` | Diseño escrito por `arquitecto-tecnico` (opus): siete filas (F1 a F7) en dos entregas con un solo PR, unas 395 líneas de producción y unas 1,000 de pruebas, 48 casos y 16 mutantes. Sonda de `ALTER TYPE … ADD VALUE` ejecutada por el orquestador en PostgreSQL 17 (el valor nuevo no se usa en la misma transacción; la recreación del tipo falla si hay filas con él); `TC-03` la repite en F1 con el PostgreSQL de las pruebas. `revisor-impacto`: sin frontera cruzada (16 contratos en verde), un hallazgo medio y seis bajos incorporados. Doce decisiones esperan a la persona dueña (D-1 a D-12) |

| 2026-11-15 | `DISEÑO PENDIENTE REVISIÓN` | `LISTO PARA EJECUTAR · entrega a` | persona dueña | Diseño aprobado con las recomendaciones de las doce decisiones (D-1 a D-12), sin cambios. El marcador `(provisional · D-n)` de `design.md` pasó a `(aprobada · D-n)`. Se ejecuta primero la entrega a (F1 a F3) |

| 2026-11-15 | `LISTO PARA EJECUTAR · entrega a` | `EN REVISIÓN · entrega a` | `/sdd-ejecutar` | Entrega a (F1 a F3) ejecutada con TDD en la rama `tkt-029b-baja-proveedores`: migración `0016` con el verbo `DAR_BAJA`, dominio, repositorio, función y interfaz de `compras`, y siembra de pruebas. Suite completa `3599 passed, 26 skipped` con un fallo de redacción en una docstring de prueba, ya corregido (las cuatro suites afectadas `28 passed`); nueve mutantes muertos, uno de ellos (`M-11`) con un test nuevo. `auditor-arquitectura` y `auditor-sql` `APROBADO` con observaciones sin bloqueo. Sin commit todavía |

| 2026-11-15 | `EN REVISIÓN · entrega a` | `LISTO PARA EJECUTAR · entrega b` | `/sdd-revisar` | Entrega a revisada y acumulada en la rama del ticket, **sin PR**. Suite completa `3603 passed, 26 skipped`; `ruff`, `mypy`, `lint-imports` y `verificar_float` limpios; `CA-12`, `CA-R1`, `CA-R2` y la parte de `CA-5` y `CA-14` de la entrega cumplidos; mutación `M-4` a `M-8`, `M-11`, `M-14` a `M-17` muerta. `auditor-arquitectura` y `auditor-sql` `APROBADO`; `auditor-codigo` `REQUIERE CAMBIOS` en la primera pasada (cuatro Menores) y `APROBADO` tras dos ciclos de corrección (`F005` y `F006` eran código de pruebas). `auditor-docs` y `auditor-seguridad` no aplican a esta entrega. La documentación (`docs/03` §10, que sigue diciendo «Veintidós verbos») es la fila F7 |

| 2026-11-16 | `LISTO PARA EJECUTAR · entrega b` | `LISTO PARA PR` | `/sdd-ejecutar` y `/sdd-revisar` | Entrega b (F4 a F7) ejecutada con TDD y revisada: ruta `POST /baja`, caso de uso, regla de dominio, borrador, tipos del cliente y documentación. Suite completa `3654 passed, 26 skipped`; `ruff`, `mypy`, `lint-imports` y `verificar_float` limpios; mutantes `M-1`, `M-2`, `M-3`, `M-9`, `M-10`, `M-12` y `M-13` muertos (`M-9` por TC-30, no por TC-42). `auditor-arquitectura` y `auditor-seguridad` `APROBADO`; `auditor-codigo` y `auditor-docs` `REQUIERE CAMBIOS` en la primera pasada y `APROBADO CON MENORES RESUELTOS SIN REAUDITAR` tras dos ciclos de corrección, con los Menores resueltos por el orquestador con el texto literal del auditor. La persona dueña aprobó añadir el ADR de `D-3` y `PA-24`. `N002` de `auditor-codigo` (renombrar once tests) se rechaza porque el diseño fija `test_tkt029b_…` para esos criterios. Ambas entregas acumuladas en la rama, sin PR todavía |

| 2026-11-16 | `LISTO PARA PR` | `PENDIENTE FUSIÓN` | `/sdd-completar` | `delta.md` escrito para el ticket entero y observaciones del proceso añadidas a `sdd/_evolucion.md`. La deuda abierta del delta recoge los tickets futuros: reactivación de proveedores (`PA-24`), índice y puerto en TKT-030 y TKT-032. Se abre el único PR del ticket; el número consta en el comentario de registro tras la fusión |

## Decisiones registradas

- **2026-11-16 · persona dueña.** Aprobados el ADR de `D-3` (`docs/adr/20261116-verbo-dar-baja-y-bajada-recreando-el-tipo.md`) y la pregunta abierta `PA-24` (reactivación y RFC de un proveedor en `BAJA`), tras los hallazgos `F001` y `F006` de `auditor-docs`.

- **2026-11-15 · persona dueña.** Aprobadas D-1 a D-12 con la recomendación de cada una. En D-3 rige la bajada que recrea el tipo tras su guarda; en D-6 se añade el escenario 13 a HDU-004 y `CA-R1` se reformula como «sin modificarse salvo el conteo de verbos» (D-7); en D-8 el ticket se ejecuta en dos entregas con un solo PR.

- **2026-11-15 · persona dueña.** TKT-029b se define antes que TKT-032, porque la pantalla del catálogo pinta el `409` de la baja y TKT-032 depende además de TKT-030 y TKT-031, que no existen.
- **2026-11-15 · persona dueña.** El puerto `CatalogoProveedores` no entra en TKT-029b: queda en TKT-030, su primer consumidor. Se corrige `docs/05` en el PR.
- **2026-11-15 · persona dueña.** La baja se asienta con un verbo nuevo `DAR_BAJA`: migración `0016`, cambio del borrador y del conteo de verbos en el mismo PR.
- **2026-11-15 · persona dueña.** La baja procede desde `ACTIVO` y desde `DESACTIVADO`; `BAJA` es terminal (desde `BAJA`, `409` `ESTADO_NO_PERMITE_OPERACION`); sin reactivación en este ticket; la baja no libera el RFC. Se añade la sección «Proveedor» a modelo de datos §14.
- **2026-11-15 · persona dueña.** `compras` publica una función mínima de lectura de órdenes pendientes en su interfaz; `proveedores` la consume con la sesión de la transacción en curso.

## Tickets futuros sugeridos

- **Reactivación de proveedores** (`DESACTIVADO` a `ACTIVO`, y qué hacer con un RFC en `BAJA`): decisión de negocio que esta spec no toma.
- **TKT-032**: pantalla del catálogo (esc. 1), reconciliar `docs/08-wireframes.md` con la baja, y la consulta proveedor × obra (esc. 11). Depende además de TKT-030 y TKT-031.
- **TKT-030**: declarar el puerto `CatalogoProveedores` y leer el proveedor con `FOR SHARE` al emitir.
