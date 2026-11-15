# Delta · TKT-019 · Esquema y migraciones del módulo compras

> [← index](_index.md) | [← impl](impl.md)

El delta no repite la implementación: declara **qué cambió en el sistema** respecto a como estaba antes. El ticket no se partió en entregas: se ejecutó en cinco filas (F1 a F5) sobre una sola rama y sale en un solo PR.

## Añadido

| Qué | Dónde | Para qué |
|---|---|---|
| Siete tablas del módulo `compras`: `requisicion`, `requisicion_renglon`, `solicitud_autorizacion`, `orden_compra`, `orden_compra_renglon`, `reprogramacion_entrega` y `folio_consecutivo`, con restricciones nombradas, claves foráneas `ON DELETE RESTRICT` y siete índices | `backend/migraciones/versions/v0014_compras_esquema.py` | Persistir requisiciones, órdenes y solicitudes de autorización para HDU-002 a HDU-005; que el motor haga cumplir los invariantes 1, 2, 8 y 9 (centro de costos, escalas de dinero, cifras no negativas y autorización con motivo, autor y momento) |
| Dos funciones y dos disparadores `BEFORE DELETE` (`trg_requisicion_borrado_solo_borrador` y `trg_requisicion_renglon_borrado_solo_borrador`) con `SQLSTATE` `IN002` | `v0014_compras_esquema.py` | Que una requisición que ya consume presupuesto no se pueda borrar y devolver su importe al disponible (`RN-03`); el del renglón lee la requisición con `FOR SHARE` |
| Privilegios por rol: sin `DELETE` en solicitud, orden, renglón de orden, reprogramación y folio; reprogramación sin `UPDATE`; folio con `SELECT` y `UPDATE` | `v0014_compras_esquema.py` | Que lo permanente lo sea en el motor (`RN-04`, `RN-06`) |
| Guardas de bajada con `LOCK TABLE … ACCESS EXCLUSIVE MODE` | `v0014_compras_esquema.py`, `v0015_semilla_folios_de_compras.py` | Que la bajada se niegue si hay solicitudes de autorización o folios emitidos, sin carrera entre la comprobación y el borrado |
| Semilla de las series `ORDEN_COMPRA` y `REQUISICION`, con `ultimo = 0` | `backend/migraciones/versions/v0015_semilla_folios_de_compras.py` | Que el primer alta tenga una fila que bloquear para numerar sin huecos |
| Tres archivos de pruebas del ticket (175 casos con el de siembra) y la evidencia de rojo, verde y mutación por fila | `backend/tests/test_tkt019_migracion.py`, `test_tkt019_restricciones.py`, `test_tkt019_privilegios.py`, `sdd/tickets/tkt-019/rojo/` | Cubrir `CA-1` a `CA-11`, `CA-R1` a `CA-R3`, con un rechazo por regla y 19 mutantes que caen |
| ADR de las requisiciones que solo se borran en borrador | `docs/adr/20261115-disparadores-de-borrado-en-compras.md` | Registrar por qué se eligieron disparadores con `IN002` frente a revocar `DELETE` |

## Modificado

| Qué | Dónde | Antes → después |
|---|---|---|
| `dnspython` | `backend/uv.lock` | 2.9.0, con el aviso `GHSA-vvf4-9x63-8xvv` de severidad alta → 2.9.2, que lo corrige; el filtro de `pip-audit` sale con 0 y `ci.yml` no cambia |
| `test_tkt010_semilla_local.py` | `test_tkt010_ca10_lo_que_no_se_siembra_queda_vacio` | Las tablas de compras no existían → las seis tablas de documentos entran en las vacías y `folio_consecutivo` debe tener exactamente las dos series en cero (actualización declarada del diseño) |
| `docs/03-modelo-datos.md` | §1, §2, §5, §13, §14 y §15 | Orden de compra con `enum estado`; `comprometido` filtrado por estado → solo `cancelada_en` se guarda y el estado se deriva; lista cerrada de referencias sin clave foránea con `solicitud_autorizacion.entidad_id`, polimórfica; invariante 8 con la excepción de `importe_disponible` y `cantidad_disponible` (decisión de la persona dueña, 2026-11-14); invariante 9 con el `CHECK` completo; borrado de borradores con `IN002`; consulta del `comprometido` con `cancelada_en IS NULL`; índices nuevos |
| `docs/02-arquitectura.md` | §8.2 | La recepción parcial escribía el estado de la orden → el estado se deriva de las cantidades |
| `docs/05-tickets-trabajo.md` | TKT-019, TKT-021 y TKT-023 | Descripciones del esquema anterior → las del esquema implementado, el aviso de `D-15` sobre cuándo se numera el folio y el criterio nuevo de `IN002` → `409` `CONFLICTO` |
| `sdd/_evolucion.md` | Observaciones, patrones y tendencias | Sin filas de TKT-019 → seis filas nuevas, las mismas de «Observaciones para `_evolucion.md`», sumadas a cuatro patrones existentes, y seis propuestas de mejora al toolkit en estado `Propuesto` |
| `docs/glosario.md` | entrada de `D-14` | Texto anterior → el de la decisión aprobada |
| `.claude/skills/conv-sql-postgres/SKILL.md`, `.claude/agents/desarrollador-sql.md`, `.claude/agents/tester-backend.md` y las copias de `.cursor/agents/` | convención de disparadores e invariantes | Sin el disparador de borrado de borradores; «Treinta y ocho invariantes» → fila nueva y «Treinta y nueve» |
| `CLAUDE.md`, `README.md`, `llms.txt` y `docs/adr/README.md` | conteo y fila de ADR | 43 ADR → 44 con la fila del ADR nuevo |
| `spec.md` y `design.md` | documentación del ticket | Decisiones provisionales y fila «Sin cambios» → decisiones aprobadas, guardas con `LOCK TABLE`, sección «¿Merece ADR?» y documentación afectada reconciliadas durante la revisión |

## Eliminado

| Qué | Dónde | Por qué era seguro quitarlo |
|---|---|---|
| Ninguno | — | — |

## Comportamiento observable nuevo

- Ninguno para un usuario ni para un integrador: el ticket no añade rutas ni código de producción en `cimenta/`. Quien opera la base ve siete tablas nuevas tras `alembic upgrade head` y las dos series de folio en cero.
- En el motor, una requisición que no está en `BORRADOR` ya no se puede borrar: el rechazo llega con `SQLSTATE` `IN002` y el nombre del disparador. Hasta que TKT-023 escriba su traductor propio de `compras`, nada lo convierte en `409`.
- Bajar la migración `0014` se niega si hay solicitudes de autorización, y bajar la `0015` si algún folio ya se emitió.

## Contrato público tocado

| Superficie | Cambio | ¿Rompe compatibilidad? |
|---|---|---|
| Esquema de base de datos | Migraciones `0014` (siete tablas, dos disparadores, privilegios) y `0015` (semilla de folios); la cabeza pasa de `0013` a `0015` | No: solo tablas nuevas |
| `docs/api/openapi.yaml` | Sin cambios. `Requisicion.folio` sigue publicándose no nulo, pero el esquema lo admite nulo en `BORRADOR` (`D-15`): TKT-021 o TKT-023 deciden cuándo se numera y, si cambia, registran el cambio del contrato | No, por ahora |
| `backend/uv.lock` | `dnspython` 2.9.0 → 2.9.2, sin tocar `pyproject.toml` | No |

## Decisiones (ADR)

Este ticket crea un ADR: [Una requisición solo se borra en borrador](../../../docs/adr/20261115-disparadores-de-borrado-en-compras.md). El diseño original decía que no lo merecía; `auditor-docs` lo observó como Mayor en la revisión, porque `D-3` descartó la alternativa de revocar `DELETE` y cambia una convención de `conv-sql-postgres`, y la persona dueña decidió crearlo el 2026-11-15. Las otras dieciocho decisiones (`D-1` a `D-19`, salvo `D-3`) las aprobó la persona dueña el mismo día y constan en `_index.md` y `design.md`.

### 2026-11-15 — Disparadores `IN002` y no la revocación de `DELETE`

**Contexto:** un privilegio de PostgreSQL no distingue estados, y borrar una requisición `EVALUADA` devolvería su importe al disponible, contra `RN-03`; pero el contrato publicado y HDU-002 escenario 2 exigen poder borrar un borrador.
**Opciones consideradas:** (A) revocar `DELETE` y que el borrador se cancele; (B) conceder `DELETE` y rechazarlo con dos disparadores que solo dejan pasar un `BORRADOR`.
**Decisión:** la B, porque respeta el contrato y la máquina de estados sin reabrir tres artefactos y protege estructura sin decidir ninguna regla.
**Evidencia:** TC-25 y TC-26 (la carrera entre borrar un renglón y evaluar la requisición, sin `sleep`) y los mutantes `M-11` a `M-13`, que caen.
**Consecuencias:** un borrador con folio que se borra deja un hueco (`D-15`); el motor no limita las transiciones de estado, que hace cumplir el caso de uso; el `409` de `IN002` lo traduce `compras`, no `presupuesto`.

→ ADR del repositorio: `docs/adr/20261115-disparadores-de-borrado-en-compras.md`, con su fila en el índice.

## Aprendizajes

| Aprendizaje | Evidencia | Dónde aplica |
|---|---|---|
| Un `CHECK` de un solo sentido deja pasar el caso inverso: hay que probar cada rama con su control positivo y su caso negativo, o el mutante que quita una rama sobrevive | `M-14` y `M-17` solo caen con las ramas `presupuesto_con_renglon` y `motivo_sin_cancelacion` | Todo `CHECK` con una condición de ida y otra de vuelta |
| Con dos `CHECK` que una misma fila viola, PostgreSQL informa el primero por orden alfabético: el test debe esperar ese nombre | `cantidad_ordenada` negativa viola `ck_…no_negativo` y `ck_…recibida_dentro_de_lo_autorizado` (docstring de TC-09) | Los rechazos por restricción de varias columnas |
| El nombre de una restricción no puede pasar de 63 caracteres: PostgreSQL lo trunca en silencio. Los nombres largos se acortan a propósito y se documentan | `ck_orden_compra_renglon_excedente_autorizado_no_negativo` mide 65; consta en el modelo de datos §13 | Cualquier restricción con tabla y regla de nombre largo |
| Una guarda de bajada debe bloquear la tabla antes de comprobar si hay datos, o una inserción concurrente pasa la guarda y se pierde | `F001` de `auditor-sql`; el patrón ya estaba en `0007`, `0010`, `0011` y `0012` | Toda migración con una guarda `DO` |
| Para probar un disparador que espera a otra transacción se sincroniza con `pg_stat_activity` (`wait_event_type = 'Lock'`) y `pg_blocking_pids`, no con `sleep` | TC-26 | Las carreras entre dos transacciones en las pruebas de integridad |
| Un tester que valida su rojo en una copia fuera del repositorio con la implementación del diseño detecta tests propios equivocados antes de la fila verde | `110 passed` en la copia, con `M-1` a `M-10` y `M-14` a `M-17` rojos antes de escribir la migración | Las filas de esquema con muchos casos parametrizados |

## Observaciones para `_evolucion.md`

Fricción del **proceso**, no del producto.

| Tema | Observación | Severidad |
|---|---|---|
| `agente` | `auditor-docs` pidió un ADR para `D-3` en la revisión, cuando el diseño decía «sin ADR» y la persona dueña había aprobado el diseño. Costó una pregunta, un ADR, el conteo de 43 a 44 en cuatro índices y una reauditoría. El diseño decidió «¿merece ADR?» sin aplicar su propio criterio sobre la alternativa descartada de la decisión central | Media |
| `comando` | El diseño dejó `docs/02-arquitectura.md` en «Sin cambios» y contradecía el estado derivado de la orden (`F001` de `auditor-docs`, Mayor). `revisor-impacto` revisa código y fronteras, no el resto de la documentación que repite un hecho que el diseño cambia | Media |
| `herramienta` | Docker Desktop estaba apagado al ejecutar: se abrió desde la sesión y el motor no arrancó solo en unos 7 minutos; la persona lo levantó. Es el segundo ticket seguido (TKT-029a) en que el gate de Docker falla | Media |
| `herramienta` | La suite completa dura unos 12 minutos y se corre dos veces (al ejecutar y al revisar). Una corrección posterior que solo toca una guarda de bajada obliga a elegir entre repetir la suite o declarar que no se repitió; `impl.md` tuvo que decirlo | Baja |
| `documentación` | Un hallazgo del auditor pedía marcar `(asumido)` un resultado que ya se había ejecutado. La spec y el diseño conservaban la marca de antes de ejecutar, y el auditor la leyó como vigente. Los marcadores `(asumido)` y «sin ejecutar» no se retiran al comprobarse | Baja |
| `agente` | Los auditores de solo lectura, instruidos de no ejecutar nada, no pudieron correr `pytest` ni el ciclo de migración: dependen de lo que registre `impl.md`. La suite completa corrió aparte, en segundo plano, mientras auditaban | Baja |

## Deuda que queda abierta

| Qué | Por qué se dejó | Ticket sugerido |
|---|---|---|
| Índice `(obra_id, estado)` sobre `solicitud_autorizacion`, que el contrato filtra con `?obra_id=` | `D-7` aprobado no lo incluye; la persona dueña aceptó la excepción el 2026-11-15 | El ticket de la bandeja de pendientes (HDU-003), con `EXPLAIN` |
| `obra_id` de la solicitud y de la orden no se contrasta en el motor con la obra de su requisición o entidad | El esquema solo garantiza que no sea nulo; derivarlo en el caso de uso evita la discrepancia | TKT-021, TKT-023 y TKT-030: derivar `obra_id` de la entidad, nunca del cuerpo, con un test de obras cruzadas |
| Traductor de `IN002` a `409` `CONFLICTO` `ESTADO_NO_PERMITE_OPERACION` en `compras` | Este ticket no tiene casos de uso; el de `presupuesto` solo conoce `IN001` y `compras` no puede importarlo | TKT-023, o TKT-021 si llega antes |
| Cuándo se numera una requisición y si el folio de un borrador puede dejar hueco; `Requisicion.folio` no nulo en el borrador OpenAPI | `D-15` deja el folio nulable solo en `BORRADOR` y delega la decisión | TKT-021 o TKT-023, que registran el cambio de contrato si lo hay |
| La máquina de estados no impide devolver una requisición numerada a `BORRADOR` y borrarla | El disparador protege el borrado, no las transiciones | TKT-021 y TKT-023: probar que la transición no existe en `dominio/` |
| Bajada de `0014` sin guarda para `requisicion`, `orden_compra`, `orden_compra_renglon` y `reprogramacion_entrega`; solo la solicitud la tiene (`D-18`) | El plan de reversa (`pg_dump`) consta en el docstring y en el diseño | Sin ticket |
| `CHECK` de un solo sentido en `solicitud_autorizacion` (una `PENDIENTE` puede traer datos de resolución) y `BLOQUEADA` con `regla_bloqueo` nula | El diseño los aceptó | Sin ticket; revisar si el caso de uso lo exige |
| `opentelemetry-api 1.45.1` con `GHSA-mf5v-w3w3-f6cg` (media) y diez avisos de Dependabot, uno alto | No son de este ticket y no fallan el pipeline | Ticket de dependencias por abrir |
| Las citas «aprobada · D-n» de `docs/` apuntan a `design.md` del ticket, que `docs/` no enlaza | Los `D-n` viven en `design.md` del ticket | Sin ticket: opcional, enlazar el diseño en la primera cita de cada sección |
| Mermaid: la sintaxis del diagrama de `docs/02` §8.2 se revisó por lectura; el extractor solo genera una página | El trabajo de CI de diagramas la validará en el PR | Se comprueba en `/sdd-completar` |

## Pull request

**Título:** `TKT-019 · Esquema y migraciones del módulo compras`
**Origen:** `agent`. El código lo escribieron agentes; la persona dueña decidió el alcance, las diecinueve decisiones del diseño y la creación del ADR.
**Cuerpo:** qué (siete tablas de `compras` con las migraciones `0014` y `0015`, la semilla de folios y la subida de `dnspython`), por qué (habilita HDU-002 a HDU-005 sin probar sus escenarios y cierra el aviso de severidad alta que ponía en rojo el trabajo «Dependencias»), criterios cubiertos (`CA-1` a `CA-11`, `CA-R1` a `CA-R3`; `CA-12` se verifica en el pipeline y `CA-13` no aplica), cómo verificarlo (`uv run pytest` desde `backend/` con Docker en marcha; `python tools/verificar_docs.py`).

**Fusión con omisión:** el registro no va en este archivo. Va en un comentario del PR que el orquestador deja justo después de la fusión, con la aprobación explícita de la persona dueña en la sesión.
