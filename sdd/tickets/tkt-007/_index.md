# TKT-007 · Bitácora transversal de solo-anexado

> Hub del ticket. Se lee **primero**, siempre.

## Estado

ARCHIVADO

## Ficha

| | |
|---|---|
| **Tipo** | Fundación |
| **Historia** | Épica 0 · Fundación. Sin historia propia; sostiene `HDU-001` esc. 22 y 23, `HDU-002` esc. 11 y `HDU-003` esc. 7, 8 y 11, que implementan los tickets consumidores |
| **Épica / sprint** | Épica 0 · Sprint 1 |
| **Puntos** | Talla S en el ticket; riesgo de subir a M por el motor de aplicación adelantado y la enmienda de TKT-006 |
| **Reglas implicadas** | Ninguna `RN-xx` de negocio se implementa. `RN-04` es su fundamento; `RNF-09` y `RNF-13` fijan privilegio mínimo y registro técnico separado |
| **Invariantes en riesgo** | 10 (núcleo). Regresión sobre 20 y 21 y sobre TKT-001 a TKT-005: `CA-R1` a `CA-R5` |
| **Módulos en alcance** | `auditoria`; toca `herramientas/conexion.py` y `tests/conftest.py` |
| **Capas en alcance** | dominio (forma de un asiento) · aplicación (servicios y consulta) · infraestructura (modelo, repositorio, motor) · interfaz publicada; sin api |
| **Depende de** | TKT-003 (ARCHIVADO) |
| **Bloquea a** | TKT-006 y todo el que asiente |
| **Rama** | `tkt-007-bitacora` |

## Artefactos

| Artefacto | Enlace | Comando | Estado |
|---|---|---|---|
| Spec | [spec.md](spec.md) | `/sdd-definir` | Escrita el 2026-10-21 |
| Design | [design.md](design.md) | `/sdd-disenar` | Aprobado el 2026-10-21 |
| Impl | [impl.md](impl.md) | `/sdd-ejecutar` | Escrito el 2026-10-21; verificado en `/sdd-revisar` |
| Delta | [delta.md](delta.md) | `/sdd-completar` | Escrito el 2026-10-21 |

## Log de estados

| Fecha | De | A | Comando | Motivo |
|---|---|---|---|---|
| 2026-10-21 | — | `SPEC PENDIENTE` | `/sdd-definir` | Spec creada. Must validado por el usuario: M1 a M8 más M9, consecuencia documental. 10 criterios `[M]`, dos `[S]` y cinco de regresión, con rechazo en cada regla. INVEST con una reserva (talla) |
| 2026-10-21 | `SPEC PENDIENTE` | `DISEÑO PENDIENTE REVISIÓN` | `/sdd-disenar` | Diseño con 10 filas en dos entregas (A: filas 1 a 6, B: 7 a 10), unas 2,180 líneas (supera el tope de ~400), sin ADR, 57 casos más 5 de regresión y 27 mutantes. El primer intento del arquitecto murió por límite de uso sin escribir nada; se relanzó. `revisor-impacto` ausente: el impacto lo hizo el arquitecto. No se ejecutó nada. Espera decisiones D-1 a D-8 |
| 2026-10-21 | `DISEÑO PENDIENTE REVISIÓN` | `LISTO PARA EJECUTAR` | aprobación humana | El usuario aprobó el diseño con todas las recomendaciones D-1 a D-8. Se ejecuta antes que TKT-006; la fila 6 de la entrega A enmienda el diseño de TKT-006 |
| 2026-10-21 | `LISTO PARA EJECUTAR` | `EN REVISIÓN` | `/sdd-ejecutar` | Entregas A y B ejecutadas (filas 1 a 10): 854 pruebas en verde con Docker (162 propias), 28 mutantes en rojo sin sobrevivientes, 15 contratos de `import-linter`. Auditoría de arquitectura y esquema: `REQUIERE CAMBIOS` con tres Menores documentales, un ciclo de corrección y reauditoría `APROBADO`; `F003` (override de `mypy`) aceptado con nota. `auditor-sql`, `revisor-impacto` y `desarrollador-aplicacion` ausentes, sustituidos. Sin commit. **El diseño de TKT-006 quedó enmendado en este cambio** |
| 2026-10-21 | `EN REVISIÓN` | `LISTO PARA PR` | `/sdd-revisar` | Suite reejecutada por el revisor: 854 pruebas en verde, y 870 tras el ciclo de corrección; `ruff`, `format`, `mypy`, 15 contratos, `verificar_float`, `verificar_docs` y una sola cabeza de Alembic en verde. Pasada independiente de arquitectura: `REQUIERE CAMBIOS` con tres Menores; el usuario decidió corregir `F001` (NUL en textos, con rojo antes) y `F003` (override de `mypy`) y anotar `F002` (`pagina` sin tope) como deuda para TKT-027; reauditoría `APROBADO`. Los 10 criterios `[M]`, los 2 `[S]` y los 5 de regresión cumplidos. `auditor-sql`, `auditor-codigo` y `auditor-docs` ausentes, sustituidos por `auditor-arquitectura` y los verificadores; `auditor-seguridad` no aplica (sin endpoint). **El PR no toca `docs/api/openapi.yaml`, pero enmienda el diseño de TKT-006: señalarlo a la persona que aprueba** |
| 2026-10-21 | `LISTO PARA PR` | `ARCHIVADO` | `/sdd-completar` | Delta y evolución escritos (observaciones nuevas en `_evolucion.md`; los patrones `agente` y `herramienta` suben de conteo y se proponen dos mejoras nuevas al toolkit); `verificar_docs.py`, `extraer_mermaid.py` y los tests de `tools/` sin problemas; `auditor-docs` y `meta-sdd` ausentes, sustituidos por los verificadores y por el orquestador; commit local; el PR lo abre una persona. **El PR enmienda el diseño y la spec de TKT-006** |

## Decisiones registradas

- 2026-10-21 · **`DENEGAR` sin recurso.** Se atribuye a quien se le denegó: `entidad_tipo = 'usuario'`, `entidad_id = usuario_id`, sin `correlacion_id`. Se descarta `sesion.id` (credencial de la cookie legible por el rol de lectura, invariante 21) y la correlación en la bitácora (API §2.7). **Enmienda el C-1 y la D-3 de TKT-006**, que el usuario había aprobado. Decidió el usuario.
- 2026-10-21 · **Motor y sesión del rol de aplicación.** Los adelanta TKT-007 en forma mínima; TKT-006 los reusa y su fila 4 se reduce. Decidió el usuario.
- 2026-10-21 · **Nombre del usuario.** `consultar_bitacora` devuelve `usuario_id`; TKT-027, que monta la ruta, completa el nombre por la interfaz de `identidad`. `usuario_id` lleva clave foránea a `usuario` `(asumido)`. Decidió el usuario.
- 2026-10-21 · TKT-007 no monta `GET /bitacora` (D-4 de TKT-006, aprobada). El usuario validó el Must, el Won't y los supuestos.

## Tickets futuros sugeridos

- **Tope superior de `pagina`** (`F002` de la revisión): decidirlo en el contrato del borrador al montar la ruta en TKT-027.
- **Retención, purga y crecimiento de la bitácora** (`PA-T9`).
- **Asiento de un intento rechazado por el motor** (`PA-T10`, `HDU-001` esc. 18): necesita un mecanismo fuera de la transacción que se deshace y un verbo, que el enum no tiene.
- **Esquema por acción de `datos_antes` y `datos_despues`**, con escala de importes (`PA-T5`).
- **Revisar el `SELECT` del rol de lectura sobre `bitacora`** (`PA-T4`).
