# Impl · TKT-019 · Esquema y migraciones del módulo compras

> [← index](_index.md) | [← design](design.md) | Siguiente: [delta.md](delta.md)

## Qué se implementó

Se subió `dnspython` de 2.9.0 a 2.9.2 en `backend/uv.lock`, con lo que el filtro de `pip-audit` deja de fallar por `GHSA-vvf4-9x63-8xvv` y no hace falta la excepción de `CA-13`. Se creó la migración `0014`, que añade las siete tablas del módulo `compras` con sus restricciones nombradas, siete índices, los dos disparadores de borrado de borradores (`IN002`) y los privilegios por rol, y la migración `0015`, que siembra las dos series de folio. Se actualizó la documentación afectada y la prueba de siembra de TKT-010. No hay Python de producción en `cimenta/`.

## Ajustes respecto al design

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-11-15 | Las guardas de bajada de `0014` y `0015` bloquean la tabla con `LOCK TABLE … IN ACCESS EXCLUSIVE MODE` dentro del bloque `DO`, antes del `EXISTS`. La fila «Bajadas» de D-18 y los textos de las guardas en `design.md` se actualizaron | Hallazgo `F001` de `auditor-sql`: sin bloqueo, una inserción concurrente entre la comprobación y el borrado se perdería. Es el patrón de `0007`, `0010`, `0011` y `0012` |

## Archivos tocados

| Archivo | Acción | Capa |
|---|---|---|
| `backend/uv.lock` | modificado (solo el bloque de `dnspython`) | dependencias |
| `backend/migraciones/versions/v0014_compras_esquema.py` | nuevo | infraestructura |
| `backend/migraciones/versions/v0015_semilla_folios_de_compras.py` | nuevo | infraestructura |
| `backend/tests/test_tkt019_migracion.py` | nuevo | pruebas |
| `backend/tests/test_tkt019_restricciones.py` | nuevo | pruebas |
| `backend/tests/test_tkt019_privilegios.py` | nuevo | pruebas |
| `backend/tests/test_tkt010_semilla_local.py` | modificado (actualización declarada de TC-B15) | pruebas |
| `docs/03-modelo-datos.md`, `docs/05-tickets-trabajo.md`, `docs/glosario.md` | modificado | documentación |
| `.claude/skills/conv-sql-postgres/SKILL.md`, `.claude/agents/desarrollador-sql.md`, `.cursor/agents/desarrollador-sql.md` | modificado (el de Cursor, regenerado) | toolkit |
| `sdd/tickets/tkt-019/` | nuevo | planificación |

## Pruebas

Los 132 casos de las filas F2 y F3, más los 5 de F4 y la aserción añadida a TC-B15, dan 175 pasados en las cuatro suites del ticket. Los nombres siguen `test_tkt019_ca<NN>_…` y `test_tkt019_car<N>_…`, porque el ticket no prueba escenarios de historia.

| # | Test | Tipo | Criterio | Antes del código | Al cerrar |
|---|---|---|---|---|---|
| TC-01 a TC-03, TC-28a | `test_tkt019_car1_…`, `test_tkt019_car2_…` (migracion) | regresión · **rechazo** (TC-28a) | `CA-R1`, `CA-R2` | FALLA | PASA |
| TC-04 a TC-12, TC-15 a TC-22 | `test_tkt019_ca01_…` a `ca10_…` (restricciones) | feliz · **rechazo** · borde | `CA-1` a `CA-10` | FALLA | PASA |
| TC-23 a TC-26 | `test_tkt019_ca11_…` (privilegios) | **rechazo** · concurrencia | `CA-11` | FALLA (14 de 22; los 8 verdes son controles) | PASA |
| TC-13, TC-14 | `test_tkt019_ca05_…` (restricciones) | feliz · **rechazo** | `CA-5` | FALLA | PASA |
| TC-27 | `test_tkt010_ca10_lo_que_no_se_siembra_queda_vacio` | regresión | `CA-R2` | FALLA | PASA |
| TC-28b, TC-29 | `test_tkt019_car1_…` (migracion) | **rechazo** · regresión | `CA-R1` | FALLA | PASA |
| TC-D1 a TC-D3 | Comandos de F1 (`rojo/fila-1.txt`) | **rechazo** · regresión | `CA-12`, `CA-R3` | filtro sale con 1 | filtro sale con 0 |

### Ciclo TDD por fila

Ejecución con subagentes: `tester-backend` escribió el rojo y `desarrollador-sql` el verde. F1 y F5 las ejecutó el orquestador y el desarrollador, sin tester: F1 es una comprobación por comando y F5 es documentación, y ninguna tiene prueba de `pytest`. Cada rojo se confirmó con la salida literal; las salidas completas viven en `sdd/tickets/tkt-019/rojo/`.

| Fila | Rojo (salida o ruta) | Ejecutó | Verde | Tabla «mutante · test que cae» |
|---|---|---|---|---|
| F1 | `rojo/fila-1.txt` · filtro sale con **1** y nombra `GHSA-vvf4-9x63-8xvv` | ejecución de un solo agente (orquestador) | filtro sale con **0** tras `uv lock --upgrade-package dnspython` | No aplica: sin código |
| F2 | `rojo/fila-2.txt` · `110 failed in 16.15s`, 0 errors | `tester-backend` · `desarrollador-sql` | `rojo/fila-2-verde.txt` · `110 passed in 14.42s` | Sí, ver «Mutación» |
| F3 | `rojo/fila-3.txt` · `14 failed, 8 passed in 5.73s`, 0 errors | `tester-backend` · `desarrollador-sql` | `rojo/fila-3-verde.txt` · `132 passed in 18.49s` | Sí, ver «Mutación» |
| F4 | `rojo/fila-4.txt` · `6 failed, 147 passed in 25.85s`, 0 errors | `tester-backend` · `desarrollador-sql` | `rojo/fila-4-verde.txt` · suite completa `3574 passed, 26 skipped in 769.18s` | Sí, ver «Mutación» |
| F5 | `rojo/fila-5.txt` · `Grep` previo: `enum estado "ABIERTA…` dentro de `ORDEN_COMPRA` y `oc.estado IN` en §15 | `desarrollador-sql` | `rojo/fila-5.txt` · `verificar_docs`: «✓ Sin problemas.» | No aplica: documentación |

Los 8 casos de F3 que pasan en rojo son los siete `TRUNCATE` de TC-24 y el control del borrador de TC-25: nacen en verde porque `0001` no concede `TRUNCATE` y porque el borrado de un borrador ya estaba permitido; se conservan como controles de regresión. TC-14 solo es rojo por su precondición (`exigir_series_sembradas`), porque sus restricciones existen desde F2 y F3.

**Tests devueltos al tester:** ninguno. Ningún desarrollador editó un test.

**Refactor:** sin refactor en ninguna fila; el código de cada migración es el literal del diseño, con dos cadenas de SQL partidas por largo de línea.

**Evidencia de ejecución al cerrar.** `docker info` responde (Docker 29.9.3). Suite completa de F4, antes de la corrección de `F001`:

```text
3574 passed, 26 skipped in 769.18s (0:12:49)
```

Tras la corrección de `F001` (solo `LOCK TABLE` en las guardas de bajada) se repitieron las cuatro suites del ticket, que cubren esas guardas, y `ruff`, `mypy` y `verificar_docs`:

```text
175 passed in 39.69s
342 files already formatted
Success: no issues found in 342 source files
✓ Sin problemas.
```

La suite completa no se repitió después de esa corrección; `/sdd-revisar` la corre de nuevo. Las 26 omitidas son las pruebas contra archivos reales de `PA-T3`, sin variable de entorno definida, y ya lo eran antes de este ticket.

### Mutación en rutas críticas

Se aplicó un mutante cada vez sobre una copia de `backend/` fuera del repositorio, con las cuatro suites del ticket (línea base 175 pasados). La huella SHA-256 de los `.py` fue la misma antes del primer mutante y tras restaurar cada uno (`43e30fa889659e8a96f487748acd869c9ee6dc48b5c138954146d1939f624029`), y `git status` quedó idéntico. Cayeron los 19 y ninguno sobrevivió. La tabla completa, con cada resumen de `pytest`, está en `rojo/mutacion.txt`.

| Mutante | Cambio | Test que cae |
|---|---|---|
| M-1 | `requisicion.tipo_partida_id` sin `NOT NULL` | `ca02_el_motor_exige_el_centro_de_costos[requisicion_sin_tipo_de_partida]` |
| M-2 | `orden_compra.obra_id` sin `NOT NULL` | `ca02_…[orden_sin_obra]` |
| M-3 | `<=` pasa a `<` en `…recibida_dentro_de_lo_autorizado` | `ca08_recibir_de_mas_…[recibe_exactamente_lo_ordenado]` |
| M-4 | el `CHECK` pierde `+ cantidad_excedente_autorizada` | `ca08_…[recibe_hasta_el_excedente]` |
| M-5 | se quita `ck_…excedente_autorizado_no_negativo` | `ca08_…[excedente_negativo]` |
| M-6 | `>= 0` pasa a `> 0` en `importe_solicitado` | `ca04_el_cero_se_admite_…[requisicion.importe_solicitado]` |
| M-7 | se quita `ck_…costo_unitario_no_negativo` | `ca04_ninguna_cifra_es_negativa[orden_compra_renglon.costo_unitario]` |
| M-8 | `CHECK (importe_disponible >= 0)` añadido | `ca04_el_disponible_admite_negativos` |
| M-9 | `resolucion_completa` solo exige el motivo | `ca06_la_resolucion_exige_motivo_actor_y_momento` (4 casos) |
| M-10 | `estado = 'PENDIENTE'` pasa a `estado <> 'RECHAZADA'` | `ca06_…` (3 casos) |
| M-11 | se quita `trg_requisicion_borrado_solo_borrador` | `ca11_solo_se_borra_un_borrador` (6 estados) |
| M-12 | se quita `trg_requisicion_renglon_borrado_solo_borrador` | `ca11_solo_se_borra_un_borrador` y `ca11_el_borrado_del_renglon_espera_al_cambio_de_estado` |
| M-13 | se quita `FOR SHARE` del disparador del renglón | `ca11_el_borrado_del_renglon_espera_al_cambio_de_estado` |
| M-14 | `…excede_ordenado_con_renglon` pierde una rama | `ca07_excede_ordenado_apunta_a_su_renglon` (3 casos) |
| M-15 | `uq_orden_compra_requisicion_id_vigente` sin `WHERE` | `ca09_una_orden_vigente_por_requisicion` |
| M-16 | se quita `ck_requisicion_folio_fuera_de_borrador` | `ca03_folio_motivo_y_regla_segun_estado[evaluada_sin_folio]` |
| M-17 | `ck_orden_compra_cancelacion_con_motivo` en un solo sentido | `ca09_cancelacion_con_motivo[motivo_sin_cancelacion]` |
| M-18 | se quita `REVOKE DELETE ON solicitud_autorizacion` | `ca11_privilegios_exactos_por_rol` y `ca11_el_rol_de_aplicacion_no_borra_lo_permanente` |
| M-19 | `0015` siembra solo `REQUISICION` | `ca05_series_sembradas_y_bloqueables` y otros cinco |

Mientras corría la mutación se añadió el bloqueo de `F001` a las guardas de bajada; esas guardas no contienen ningún mutante, y se repitió la corrida completa sobre la versión nueva con el mismo resultado.

## Modelo por paso

| Paso | Agente | Modelo previsto | Modelo usado | Motivo del cambio |
|---|---|---|---|---|
| F1 | orquestador | `haiku` | modelo del orquestador | Tarea mecánica verificable por comando; no se despachó |
| F2 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| F2 · verde | `desarrollador-sql` | `sonnet` | `sonnet` | Disparador de §14.2: regla de dinero o de límite |
| F3 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| F3 · verde | `desarrollador-sql` | `sonnet` | `sonnet` | Disparador de §14.2: disparador de inmutabilidad y permisos |
| F4 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| F4 · verde | `desarrollador-sql` | `haiku` | `haiku` | — |
| F5 | `desarrollador-sql` | `haiku` | `haiku` | — |
| Mutación | `tester-backend` | `sonnet` | `sonnet` | — |
| Auditorías | `auditor-arquitectura`, `auditor-sql` | `sonnet` | `sonnet` | — |
| Corrección `F001` | `corrector-revision` | `haiku` | `haiku` | — |
| Revisión · reauditoría SQL, seguridad, docs | `auditor-sql`, `auditor-seguridad`, `auditor-docs` | `sonnet` · `sonnet` · `haiku` | igual | — |
| Revisión · corrección de docs | `corrector-revision` | `haiku` | `haiku` | — |

## Resultado contra los criterios de aceptación

| Criterio | Nivel | Estado | Evidencia |
|---|---|---|---|
| `CA-1` a `CA-4` | `[M]` | Cumplido | TC-04 a TC-11 |
| `CA-5` | `[M]` | Cumplido | TC-12 a TC-14 |
| `CA-6`, `CA-7` | `[M]` | Cumplido | TC-15 a TC-17 |
| `CA-8`, `CA-9`, `CA-10` | `[M]` | Cumplido | TC-18 a TC-22 |
| `CA-11` | `[M]` | Cumplido | TC-23 a TC-26 |
| `CA-12` | `[M]` | Cumplido localmente; la comprobación en el pipeline se verifica en `/sdd-completar` | TC-D1 |
| `CA-13` | `[M]` | No aplica: existe la versión corregida 2.9.2, por lo que no se añade `--ignore-vuln` | `rojo/fila-1.txt` y consulta de `auditor-arquitectura` a OSV (`fixed: 2.9.2`) |
| `CA-R1`, `CA-R2` | `[M]` | Cumplido | TC-01 a TC-03, TC-27, TC-28, TC-29 |
| `CA-R3` | `[M]` | Cumplido | Suite completa de F4: `3574 passed, 26 skipped`; `git diff -- backend/uv.lock` solo cambia el bloque de `dnspython` |

## Auditorías

| Auditor | Veredicto | Hallazgos | Ciclos |
|---|---|---|---|
| `auditor-arquitectura` | `APROBADO` | 3 observaciones | 1 |
| `auditor-sql` | `APROBADO` en la reauditoría | 2 Menores: `F001` resuelto, `F002` excepción aceptada | 2 |
| `auditor-seguridad` | `APROBADO` | 3 observaciones de severidad baja | 1 |
| `auditor-docs` | `APROBADO CON MENORES RESUELTOS SIN REAUDITAR` | 2 Mayores y 3 Menores resueltos; 2 Menores resueltos por el orquestador | 2 |

### Hallazgos y su resolución

| ID | Auditor | Severidad | Ubicación | Hallazgo | Estado |
|---|---|---|---|---|---|
| F001 | `auditor-arquitectura` | Observación | `sdd/tickets/tkt-019/` | Faltaba la tabla de mutantes | Resuelto: tabla de «Mutación en rutas críticas» |
| F002 | `auditor-arquitectura` | Observación | `v0014_compras_esquema.py:242-252` | Varias claves foráneas sin índice, entre ellas las que filtrará HDU-003 | Aceptado: es el D-7 aprobado; el ticket de la bandeja añade `(obra_id, estado)` con `EXPLAIN` |
| F003 | `auditor-arquitectura` | Observación | disparadores de `v0014` | Los disparadores deciden por estado, y nada en el motor limita las transiciones de estado | Aceptado: D-3 aprobado; la máquina de estados la hace cumplir el caso de uso de TKT-021 o TKT-023 |
| F001 | `auditor-sql` | Menor | `v0014:322-330`, `v0015:25-27` | Guardas de bajada sin bloqueo entre comprobación y borrado | Resuelto: `LOCK TABLE … ACCESS EXCLUSIVE MODE`; reauditado y aprobado |
| F002 | `auditor-sql` | Menor | `v0014:242-252` | `solicitud_autorizacion.obra_id` sin índice y el contrato publica el filtro `?obra_id=` | Excepción aceptada por la persona dueña el 2026-11-15: contradice el D-7 que aprobó; el ticket de la bandeja añade el índice con `EXPLAIN`. Baja a Observación |
| F001 a F003 | `auditor-seguridad` | Baja | `v0014` | `obra_id` de la solicitud y de la orden no se contrasta con la de su requisición; una transición a `BORRADOR` que el motor no impide | Aceptado: obligaciones de TKT-021, TKT-023 y TKT-030, ya declaradas en el diseño |
| F001 | `auditor-docs` | Mayor | `docs/02-arquitectura.md` §8.2 | La secuencia de recepción escribía el estado de la orden | Resuelto por `corrector-revision`; reclasificado Resuelto |
| F002 | `auditor-docs` | Mayor | `docs/adr/` | Faltaba el ADR de D-3, que descartó la revocación de `DELETE` | Resuelto: ADR `20261115-disparadores-de-borrado-en-compras.md`, con su fila en el índice y el conteo de 43 a 44, por decisión de la persona dueña |
| F003 | `auditor-docs` | Menor | `docs/05-tickets-trabajo.md` | El criterio de `dnspython` seguía condicionado a `CA-13` | Resuelto por el orquestador: el criterio dice «Comprobado el 2026-11-15 con `pip-audit`». El auditor pedía marcarlo `(asumido)`, pero el resultado sí se ejecutó (`rojo/fila-1.txt`) |
| F004, F005 | `auditor-docs` | Menor | `docs/03-modelo-datos.md`, `spec.md` | Folios sin huecos sin calificar; «provisionales hasta el gate» vigente | Resuelto; reclasificado Resuelto |
| F006 | `auditor-docs` | Menor | `design.md` «Documentación afectada» | La fila marcaba «Sin cambios» documentos que cambiaron | Resuelto por el orquestador con el texto literal del auditor |

Las observaciones `O-1` a `O-5` de `auditor-sql` (bajada sin guarda en tablas distintas de la solicitud, transición a `BORRADOR` que el motor no impide, y huecos que el diseño aceptó) y las `O1` a `O6` de `auditor-docs` no bloquean y se trasladan a la deuda del delta. `O1` (conteo de invariantes) se corrigió.

## Hallazgos fuera de alcance

Detectados de paso. **No se implementan aquí.**

| Archivo | Observación | Prioridad |
|---|---|---|
| `.claude/skills/conv-sql-postgres/SKILL.md:8` | Dice «Treinta y ocho invariantes» y el modelo de datos dice 39. Ya era así antes del ticket | Baja |
| `docs/api/openapi.yaml` · `Requisicion.folio` | Publica folio no nulo en `BORRADOR`; con D-15 el esquema lo permite nulo. TKT-021 o TKT-023 deciden cuándo se numera y, si cambia el contrato, lo registran | Media, para ese ticket |
| `docs/03-modelo-datos.md` §5 «los folios no tienen huecos» | Un `BORRADOR` con folio que se borra dejaría un hueco; el aviso de D-15 ya está en TKT-021 y TKT-023 | Media, para esos tickets |
| `docs/05-tickets-trabajo.md` TKT-019 | Describe el bump de `dnspython` como condicionado a `CA-13`; la versión corregida existe y el bump se hizo sin excepción | Baja; se reconcilia en `/sdd-completar` |
| Repositorio | Diez avisos de Dependabot, uno alto, no son de este ticket | Baja |

## Documentación actualizada

| Documento | Qué cambió |
|---|---|
| `docs/03-modelo-datos.md` | §1, §2, §5 (diagrama y prosa), §13 (invariantes 8, 9 y 14), §14 y §15 (consulta del `comprometido` e índices) |
| `docs/05-tickets-trabajo.md` | TKT-019, TKT-021 y TKT-023 |
| `docs/glosario.md` | Entrada de D-14 |
| `.claude/skills/conv-sql-postgres/SKILL.md` y `.claude/agents/desarrollador-sql.md` | Fila del disparador de borrado de borradores (`IN002`); `.cursor/agents/` regenerado |

`python tools/verificar_docs.py` → «✓ Sin problemas.»

## Verificación final

Resultado de la revisión del 2026-11-15, con las cifras de la última corrida:

```text
docker info → 29.9.3
uv run pytest → 3574 passed, 26 skipped in 720.50s (0:12:00)
uv run ruff check . → All checks passed!
uv run mypy cimenta/ → Success: no issues found in 149 source files
uv run lint-imports → Contracts: 16 kept, 0 broken.
python tools/verificar_docs.py → ✓ Sin problemas.
```

La suite completa corrió después de la corrección de `F001` de `auditor-sql`. Las 26 omitidas son las pruebas contra archivos reales de `PA-T3` y no cambian. La salida completa está en `rojo/revision-suite.txt`.

| Criterio | Nivel | Resultado |
|---|---|---|
| `CA-1` a `CA-11` | `[M]` | Cumplidos, con rojo registrado y verde; 175 casos en las cuatro suites del ticket |
| `CA-12` | `[M]` | Cumplido localmente (filtro con 0); la comprobación del trabajo «Dependencias» de `ci.yml` se verifica en `/sdd-completar` |
| `CA-13` | `[M]` | No aplica: 2.9.2 corrige el aviso |
| `CA-R1` a `CA-R3` | `[M]` | Cumplidos; suite completa en verde con la versión nueva de `dnspython` |

- [x] Todos los criterios `[M]` cumplidos con evidencia (`CA-12` se cierra en el pipeline)
- [x] Ciclo TDD completo en cada fila con prueba: rojo antes de verde, ningún test editado por un desarrollador
- [x] Suite en verde, con la salida pegada arriba
- [x] ≥1 test de rechazo por regla implicada
- [x] Mutación en rutas críticas: 19 de 19 cayeron
- [x] Todas las auditorías `APROBADO` (`auditor-docs` con menores resueltos sin reauditar: `F003` y `F006`, comunicados a la persona dueña)
- [x] Sin hallazgo crítico o mayor pendiente
- [x] Documentación afectada actualizada en este mismo cambio
- [x] `ruff`, `mypy`, `lint-imports` limpios
- [x] Rama `tkt-019-esquema-compras`; `git-entrega` repetirá el escaneo de secretos al commitear
