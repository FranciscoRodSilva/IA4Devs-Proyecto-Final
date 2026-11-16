# Impl · TKT-029b · Baja protegida de proveedores

> [← index](_index.md) | [← design](design.md) | Siguiente: `delta.md` (se enlaza en `/sdd-completar`)

## Entrega a · bitácora y `compras` (F1 a F3)

### Qué se implementó

La entrega a deja lista la base sobre la que la baja se apoya, sin ninguna ruta nueva. La migración `0016` añade el verbo `DAR_BAJA` al final del `ENUM` `accion_bitacora`, y `AccionBitacora` (Python) y el borrador de la API lo reciben en el mismo orden. El módulo `compras`, que no tenía código, publica en su interfaz una función de solo lectura, `ordenes_pendientes_de_proveedor`, que lee los renglones de las órdenes vivas de un proveedor con la sesión de la transacción en curso y deriva el estado de cada orden con una regla pura de dominio (`ABIERTA`, `PARCIAL`, `CERRADA`). La entrega b construirá encima la regla de la baja, el caso de uso, la ruta y la documentación.

### Ajustes respecto al design

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-11-15 | TC-17 no compara `xact_commit`: comprueba que `txid_current_if_assigned()` sigue nulo tras la función y que un `UPDATE` en esa transacción de solo lectura responde `25006` | Las estadísticas de `pg_stat_database` se vacían de forma asíncrona y dentro de una transacción se cachean, así que `xact_commit` es inestable. El identificador de transacción prueba la misma garantía: la función no escribe |
| 2026-11-15 | Un test nuevo en `test_tkt029b_ordenes_pendientes.py`: ocho órdenes `ABIERTA` con folios en orden inverso, que mata a `M-11` | Con solo dos órdenes pendientes (TC-14) un orden por `id` pasaba la mitad de las veces por azar (cuatro corridas alternaron `1 failed` y `8 passed`) |
| 2026-11-15 | La docstring de `test_tkt029b_migracion.py` dejó de contener la cadena `create_all()` | La suite completa falló en `test_tkt003_ca09_esc01_esquema_sin_creacion_automatica`, que busca esa cadena en todos los archivos de pruebas. Es un error de redacción del propio test, no de comportamiento |
| 2026-11-15 | La fila F2 nace en rojo por `ModuleNotFoundError` del módulo nuevo `compras/dominio/orden_compra.py` | El diseño lo declara así («el módulo no existe»). El comportamiento lo cubren los mutantes `M-4`, `M-5` y `M-6` |
| 2026-11-15 | La siembra deriva el folio de la requisición quitando el prefijo `OC-` (`OC-T029B-0001` pasa a `REQ-T029B-0001`) y no crea `requisicion_renglon` | El diseño dice «el sufijo del folio» sin fijarlo, y ni el esquema ni el diseño exigen renglones de requisición |
| 2026-11-15 | `TC-14` y `TC-15` llevan `test_hdu004_esc12_…` | La columna «Escenario» del diseño lo dice; la nota de nombres sugería `test_tkt029b_…` para `CA-12`. Se siguió la columna |

### Archivos tocados

| Archivo | Acción | Capa |
|---|---|---|
| `backend/migraciones/versions/v0016_auditoria_verbo_dar_baja.py` | nuevo | infraestructura |
| `backend/cimenta/auditoria/dominio/asiento.py` | modificado | dominio |
| `docs/api/openapi.yaml` | modificado (`DAR_BAJA` en `AccionBitacora`) | contrato |
| `backend/cimenta/compras/dominio/orden_compra.py` | nuevo | dominio |
| `backend/cimenta/compras/infraestructura/tablas.py` | nuevo | infraestructura |
| `backend/cimenta/compras/infraestructura/repositorio_orden_compra.py` | nuevo | infraestructura |
| `backend/cimenta/compras/aplicacion/ordenes_pendientes.py` | nuevo | aplicación |
| `backend/cimenta/compras/interfaz.py` | modificado | aplicación (interfaz publicada) |
| `backend/herramientas/soporte_tkt029b_ordenes.py` | nuevo | pruebas (siembra) |
| `backend/tests/test_tkt029b_migracion.py` | nuevo | pruebas |
| `backend/tests/test_tkt029b_dominio_orden.py` | nuevo | pruebas |
| `backend/tests/test_tkt029b_ordenes_pendientes.py` | nuevo | pruebas |
| `backend/tests/test_tkt007_dominio.py` (`:434`), `test_tkt007_esquema.py` (`:262`, `:268`, `:543`), `test_tkt007_fronteras.py` (`:247`) | modificados: `22` pasa a `23` (decisión `D-7`) | pruebas |

### Pruebas

| # | Test | Tipo | Criterio | Antes del código | Al cerrar |
|---|---|---|---|---|---|
| TC-01 | `test_tkt029b_car1_0016_cuelga_de_0015_y_la_cabeza_es_unica` | regresión | `CA-R1` | FALLA | PASA |
| TC-02 | `test_tkt029b_car1_ca14_el_tipo_gana_dar_baja_al_final_y_el_rol_de_aplicacion_lo_asienta` | feliz · permisos | `CA-R1`, `CA-14` | FALLA | PASA |
| TC-03 | `test_tkt029b_car1_sonda_add_value_no_se_usa_en_su_transaccion_y_queda_al_final` | sonda del motor | `CA-R1` | PASA por diseño | PASA |
| TC-04 | `test_tkt029b_car1_la_bajada_devuelve_los_22_verbos_y_deja_la_bitacora_como_estaba` | regresión | `CA-R1` | FALLA | PASA |
| TC-05 | `test_tkt029b_car1_la_bajada_se_niega_con_asientos_dar_baja` | **rechazo** | `CA-R1` | FALLA | PASA |
| TC-06 | `test_tkt029b_car1_sube_baja_y_vuelve_a_subir` | regresión | `CA-R1` | FALLA | PASA |
| TC-07 | `test_tkt029b_car1_tras_la_bajada_el_rol_de_aplicacion_conserva_sus_privilegios` | permisos | `CA-R1` | FALLA | PASA |
| TC-08 | las cinco afirmaciones de TKT-007 con `23` | regresión | `CA-R1`, `CA-14` | FALLA (`assert 22 == 23`) | PASA |
| TC-09 a TC-13 | `test_hdu004_esc12_tc09…tc11_*` y `test_tkt029b_tc12…tc13_*` (11 tests) | feliz, **rechazo** (lo que no es pendiente) y borde | `CA-5`, `CA-12` | FALLA (módulo ausente) | PASA |
| TC-14 | `test_hdu004_esc12_ordenes_pendientes_devuelve_la_parcial_y_la_abierta_por_folio` y el test de ocho órdenes | feliz | `CA-12` | FALLA | PASA |
| TC-15 | `test_hdu004_esc12_cancelada_cerrada_o_ajena_no_es_pendiente[…]` (3 casos) | **rechazo** | `CA-5`, `CA-12` | FALLA | PASA |
| TC-16 | `test_tkt029b_orden_viva_sin_renglones_no_es_pendiente` | borde | `CA-5` | FALLA | PASA |
| TC-17 | `test_tkt029b_lectura_de_pendientes_corre_en_solo_lectura_y_no_escribe` | feliz | `CA-12` | FALLA | PASA |
| TC-18 | `test_tkt029b_lectura_de_pendientes_usa_la_sesion_recibida` | feliz | `CA-12` | FALLA | PASA |
| TC-19 | `test_tkt029b_interfaz_de_compras_publica_solo_la_lectura_y_proveedores_no_la_salta` | **rechazo** · frontera | `CA-12`, `CA-R2` | FALLA | PASA |

### Ciclo TDD por fila

| Fila | Rojo (salida o ruta) | Ejecutó | Verde | Tabla «mutante · test que cae» |
|---|---|---|---|---|
| F1 | [rojo/fila-1.txt](rojo/fila-1.txt) | `tester-backend` · `desarrollador-sql` | Fila F1 · Verde | Sí |
| F2 | [rojo/fila-2.txt](rojo/fila-2.txt) | `tester-backend` · `desarrollador-dominio` | Fila F2 · Verde | Sí |
| F3 | [rojo/fila-3.txt](rojo/fila-3.txt) | `tester-backend` · `desarrollador-aplicacion` | Fila F3 · Verde | Sí |

#### Fila F1 · Migración `0016` y verbo `DAR_BAJA`

**Rojo** (`rojo/fila-1.txt`, resumen literal; TC-03 pasa por diseño y la salida omite los tests que pasan):

```text
======================== 11 failed, 82 passed in 8.34s ========================
```

Seis fallos en `test_tkt029b_migracion.py` por `exigir_revision("0016")` («Falta la migración 0016 … Alembic no la conoce») y cinco en TKT-007 por `assert 22 == 23`. Ninguno por importación, sintaxis o entorno.

**Verde:** `uv run pytest` sobre los doce archivos de la fila (`test_tkt029b_migracion`, las seis suites de TKT-007 que migran, `test_tkt019_migracion`, `test_tkt029a_migracion` y las cuatro de identidad y permisos): `187 passed in 23.88s`. `ruff format`: `344 files left unchanged`; `ruff check`: `All checks passed!`; `mypy`: `Success: no issues found in 344 source files`; `lint-imports`: `Contracts: 16 kept, 0 broken.` `npm run tipos:generar` y `npm run tipos:verificar` (`Tipos al día.`) no cambiaron nada, como anticipó el revisor de impacto.

**Refactor:** sin refactor; el código mínimo ya seguía el patrón de `0003` y `0015`.

**Tests devueltos al tester:** ninguno.

**Sonda del supuesto 5 (TC-03), contra el PostgreSQL de las pruebas con el rol de migración:** `ADD VALUE` y uso inmediato en la misma transacción responden `55P04`; tras `ROLLBACK` el valor no existe; confirmado y usado en otra transacción funciona y queda último en `enumsortorder`. El motor no contradice el diseño, así que la fila no se escaló. La sonda previa del orquestador sobre PostgreSQL 17 dio el mismo resultado.

#### Fila F2 · Dominio de la orden de compra

**Rojo** (`rojo/fila-2.txt`): `11 failed in 0.04s`, todos por `ModuleNotFoundError: No module named 'cimenta.compras.dominio.orden_compra'`. Es el rojo que el diseño declara para un módulo nuevo; el comportamiento lo comprueban los mutantes de abajo.

**Verde:** `11 passed in 0.04s`; `lint-imports`: `16 kept, 0 broken`; `verificar_float`: `archivos revisados: 40; hallazgos: 0`; `ruff` y `mypy` limpios (`346 files`).

**Refactor:** `esta_pendiente` pasó de comparar `estado.value` contra un `frozenset` de cadenas a comparar contra los miembros del enum; se eliminó la constante `_PENDIENTES`. La suite siguió en verde.

**Tests devueltos al tester:** ninguno.

#### Fila F3 · Lectura de órdenes pendientes de `compras`

**Rojo** (`rojo/fila-3.txt`): `8 failed in 3.07s`. Seis tests caen con `ImportError: cannot import name 'OrdenPendiente' | 'ordenes_pendientes_de_proveedor' from 'cimenta.compras.interfaz'` y `TC-19` con `assert None == ['OrdenPendiente', 'ordenes_pendientes_de_proveedor']`. Es la razón esperada: el símbolo no está en la interfaz. La siembra y el esquema se validaron antes con una sonda desechable (`CHECK` de recibido dentro de lo autorizado, `25006` en solo lectura).

**Verde:** `128 passed in 15.15s` (los dos archivos nuevos de `compras` y `test_tkt019_restricciones.py`); `ruff format --check`: `351 files already formatted`; `ruff check`: `All checks passed!`; `mypy`: `Success: no issues found in 351 source files`; `lint-imports`: `16 kept, 0 broken`; `verificar_float`: `hallazgos: 0`.

**Refactor:** `Session` pasó de importarse bajo `TYPE_CHECKING` a importarse directamente en `ordenes_pendientes.py`, como en el repositorio.

**Tests devueltos al tester:** ninguno.

**Evidencia de ejecución al cerrar la entrega (suite completa, con `docker info` respondiendo, servidor 29.9.3):**

```text
FAILED tests/test_identidad_sin_create_all.py::test_tkt003_ca09_esc01_esquema_sin_creacion_automatica
1 failed, 3599 passed, 26 skipped in 721.36s (0:12:01)
```

El único fallo era la cadena `create_all()` en la docstring de `test_tkt029b_migracion.py`. Tras reescribir esa frase, las cuatro suites afectadas dan `28 passed in 5.41s`. No se repitió la suite completa de doce minutos; la corrida de `/sdd-revisar` y la del cierre de la entrega b la repiten. Los 26 `skipped` son las pruebas contra archivos reales de catálogo (`CIMENTA_CATALOGO_*` sin definir), que ya existían.

### Mutación en rutas críticas

Copia previa fuera del repositorio, huella SHA-256 de todos los `.py` de `backend/` antes y después de cada mutante (idéntica en todos), un mutante a la vez y restauración tras cada uno. Huella inicial `f739d53e…`; desde `M-11` es `18c58382…` porque se añadió el test de ocho órdenes.

| Mutante | Cambio | Test que cae |
|---|---|---|
| `M-4` | `recibida < ordenada` pasa a `<=` | `test_hdu004_esc12_tc11_renglon_completo_es_cerrada`, `…tc11_renglon_sin_saldo_con_renglon_en_cero_es_cerrada`, `test_tkt029b_tc13_recibido_igual_a_ordenada_en_otra_escala_es_cerrada` y TC-14 |
| `M-5` | `recibida < ordenada` pasa a `!=` | `test_hdu004_esc12_tc11_excedente_autorizado_es_cerrada` y `…[cerrada_con_excedente_autorizado]` |
| `M-6` | `recibida > 0` pasa a `>=` | `…tc09_un_renglon_sin_recibir_es_abierta`, `…tc09_dos_renglones_sin_recibir_son_abierta`, TC-14, TC-17 y TC-18 |
| `M-7` | se quita `cancelada_en IS NULL` | TC-14 y `…[cancelada_sin_nada_recibido]` |
| `M-8` | se quita el filtro por `proveedor_id` | TC-14 y `…[abierta_de_otro_proveedor]` |
| `M-11` | orden por `id` en lugar de folio | `…con_muchas_ordenes_sale_por_folio_y_no_por_id` (nuevo; cayó cuatro de cuatro corridas). Sobrevivía a TC-14 la mitad de las veces |
| `M-14` | la guarda de la bajada pasa a `IF FALSE` | TC-05 |
| `M-15` | se quita `DROP TYPE accion_bitacora_0016` | TC-04 |
| `M-16` | la función abre una sesión propia | TC-18 (el `OperationalError` en la salida es ruido del cierre del mutante) |
| `M-17` (añadido en la revisión) | la agrupación por orden se sustituye por evaluación renglón a renglón | `test_hdu004_esc12_orden_de_dos_renglones_con_uno_completo_y_otro_sin_recibir_es_una_parcial` y `test_hdu004_esc12_orden_de_dos_renglones_sin_recibir_es_una_sola_abierta`, tests nuevos: `2 failed, 9 passed`. Antes de ellos, todas las órdenes sembradas tenían un solo renglón y el mutante sobrevivía. Huella del archivo mutado `99d77cee…` antes y después de revertir; huella de los 351 `.py` `59a5d2d0…` antes y después |

`auditor-arquitectura` repitió `M-4`, `M-5`, `M-6`, `M-7`, `M-8`, `M-11`, `M-14`, `M-15` y `M-16` por su cuenta, más un mutante de `esta_pendiente` sin `PARCIAL`, y todos cayeron.

### Modelo por paso

| Paso | Agente | Modelo previsto | Modelo usado | Motivo del cambio |
|---|---|---|---|---|
| Rama | `git-entrega` | `haiku` | `haiku` | — |
| F1 · rojo | `tester-backend` | `sonnet` | `sonnet` | — |
| F1 · verde | `desarrollador-sql` | `sonnet` | `sonnet` | Disparador del diseño: bitácora de solo anexado y permisos de rol |
| F2 · rojo | `tester-backend` | `haiku` | `haiku` | — |
| F2 · verde | `desarrollador-dominio` | `haiku` | `haiku` | — |
| F3 · rojo | `tester-backend` | `haiku` | `haiku` | — |
| F3 · verde | `desarrollador-aplicacion` | `haiku` | `haiku` | — |
| Cierre: suite y mutación | `tester-backend` | `sonnet` | `sonnet` | — |
| Auditoría | `auditor-arquitectura`, `auditor-sql` | `sonnet` | `sonnet` | — |

### Auditorías de la entrega a

| Auditor | Veredicto | Hallazgos | Ciclos |
|---|---|---|---|
| `auditor-arquitectura` | `APROBADO` | Tres observaciones sin bloqueo (`O-1` a `O-3`) | 1 |
| `auditor-sql` | `APROBADO` | Cuatro observaciones sin bloqueo (`O-01` a `O-04`) | 1 |
| `auditor-codigo` | `APROBADO` | `F001` a `F004` (Menores) y `F005` y `F006` (código de pruebas) resueltos; una observación `O-1` resuelta | 3 (primera pasada, reauditoría y ciclo 2 acotado) |

**`auditor-codigo`.** Primera pasada `REQUIERE CAMBIOS`: `F001` (tres docstrings de TKT-007 decían «22 verbos»; a «23»), `F002` (ninguna prueba cubría la agrupación por orden; dos tests nuevos de dos renglones, que matan a `M-17`), `F003` (el docstring de `estado_derivado` no empezaba con «Implementa CA-5 y CA-12 de TKT-029b»; corregido con el texto literal del auditor) y `F004` (imports perezosos obsoletos y una docstring confusa del TC-10; subidos al encabezado). La reauditoría los dio por `Resuelto` y añadió `F005` (un `cast` sin comprobar `None` ni explicar, en TC-18) y `F006` (un `# type: ignore[arg-type]` sin motivo en `test_tkt029b_migracion.py`), que `corrector-revision` corrigió con el texto literal; el ciclo 2 los dio por resueltos y dejó una observación de redacción de la lista de mutantes, que el orquestador resolvió. Ningún Mayor sobre código de producción.

Observaciones aceptadas del `auditor-codigo`: `fotografia` está copiada en once archivos de prueba y el alias `Conexion` también (el diseño autoriza copiarlas); `Row[*tuple[Any, ...]]` es el patrón de los repositorios del proyecto; `.quantize` de la siembra sin modo de redondeo con entradas de cuatro decimales (exacto); `v0016` sin `from __future__ import annotations`. El mismo `# type: ignore[arg-type]` sin motivo persiste en `test_tkt019_migracion.py`, `test_tkt029a_migracion.py` y `test_tkt059_migracion.py`, de tickets ya fusionados: no se tocan aquí.

| ID | Auditor | Severidad | Ubicación | Hallazgo | Estado |
|---|---|---|---|---|---|
| O-1 · O-04 | arquitectura · sql | Observación | `docs/03-modelo-datos.md:1012` | §10 sigue diciendo «Veintidós verbos» | Se cierra en F7 (entrega b); el PR es único y no se fusiona sin ello |
| O-2 | arquitectura | Observación | `sdd/tickets/tkt-029b/` | Faltaba `impl.md` con la tabla de mutantes | Resuelto con este archivo |
| O-3 | arquitectura | Observación | `test_tkt029b_ordenes_pendientes.py:46` | La docstring promete importar los símbolos dentro de cada caso, pero `EstadoOrden` se importa al cargar | Sin cambio; inocuo, porque el módulo ya existe |
| O-01 | sql | Observación | `repositorio_orden_compra.py:58-61` | `orden_compra.proveedor_id` no tiene índice; `EXPLAIN` usa el índice parcial de órdenes vivas con `Filter` | Aceptada (`D-9`); TKT-032 crea `ix_orden_compra_proveedor_id` con su medición |
| O-02 | sql | Observación | `v0016_auditoria_verbo_dar_baja.py:56` | La bajada reescribe `bitacora` bajo `ACCESS EXCLUSIVE` | Aceptada (`D-3`); operación excepcional con plan de reversa documentado |
| O-03 | sql | Observación | `repositorio_orden_compra.py:63` | `COLLATE "C"` no usa `uq_orden_compra_folio`; se ordena en memoria un conjunto ya filtrado | Aceptada (`D-12`) |

**Qué verificó `auditor-sql`** (ciclo ejecutado contra `postgres:18.6` desechable con el rol `cimenta_migracion`): `upgrade head` deja `0016` con 23 verbos y `DAR_BAJA` último; `downgrade -1` devuelve `0015` con los 22 de `0003` en su orden, `relacl` de `bitacora` idéntico y sin tipo temporal; un segundo `upgrade head` vuelve a `0016` con el mismo `relacl`. Los cuatro puntos de bloqueo, reversibilidad, privilegios e inmutabilidad quedaron descartados con evidencia.

**Qué verificó `auditor-arquitectura`:** `lint-imports` (16 contratos, 0 rotos), `ruff`, `mypy`, `verificar_float` (40 archivos, 0 hallazgos), `verificar_docs` y las reglas 1, 2, 3, 4, 7, 8, 11, 14 y 17 de `CLAUDE.md` una por una, y que la definición de «pendiente» sale de HDU-004 esc. 12, `D-1` y `D-2` aprobadas, sin regla inventada.

### Hallazgos fuera de alcance

| Archivo | Observación | Prioridad |
|---|---|---|
| `docs/03-modelo-datos.md` §10 | Pasar a «Veintitrés verbos» y añadir la frase de la técnica de `ADD VALUE` | Alta antes de fusionar (F7) |

### Documentación actualizada

Ninguna en la entrega a: la documentación afectada es la fila F7 de la entrega b.

`python tools/verificar_docs.py` → `✓ Sin problemas.`

## Verificación final · entrega a

Corridas del 2026-11-15, con `docker info` respondiendo (servidor 29.9.3), sobre el árbol tras el último ciclo de corrección. Las cifras son las de esa última corrida.

```text
$ uv run pytest -p no:cacheprovider -q            (desde backend/, suite completa)
3603 passed, 26 skipped in 672.25s (0:11:12)

$ uv run ruff format --check .
351 files already formatted
$ uv run ruff check .
All checks passed!
$ uv run mypy .
Success: no issues found in 351 source files
$ uv run lint-imports
Contracts: 16 kept, 0 broken.
$ uv run python -m herramientas.verificar_float
archivos revisados: 40; hallazgos: 0
$ python tools/verificar_docs.py
✓ Sin problemas.
```

Los 26 `skipped` son las pruebas contra archivos reales de catálogo (`CIMENTA_CATALOGO_*` sin definir, `PA-T3`), que ya existían. Frente a la corrida previa a la revisión (`3601 passed`), suman dos tests nuevos de la fila F3 (`F002`).

| Criterio | Nivel | Estado | Evidencia |
|---|---|---|---|
| `CA-12` (función de lectura de `compras` por su interfaz, con la sesión en curso, sin escribir) | `[M]` | Cumplido | TC-14 a TC-19 y los dos tests de dos renglones |
| `CA-5` (qué cuenta como «pendiente»), a nivel de la regla y de la función; el rechazo por HTTP llega en la entrega b (TC-35) | `[M]` | Cumplido en esta entrega | TC-09 a TC-13, TC-15, TC-16 |
| `CA-14` (el verbo `DAR_BAJA` coincide en la base, Python y el borrador), parte de la entrega a | `[M]` | Cumplido en esta entrega | TC-02, TC-08 |
| `CA-R1` (la cadena de migraciones, privilegios y el esquema anterior no se rompen) | `[M]` | Cumplido | TC-01 a TC-08; suites de TKT-007, TKT-019 y TKT-029a en verde |
| `CA-R2` (ninguna frontera cruzada) | `[M]` | Cumplido | TC-19; `lint-imports` `16 kept, 0 broken` |
| `CA-1` a `CA-4`, `CA-6` a `CA-11`, `CA-13`, `CA-R3`, `CA-R4` | `[M]` | Pendiente: entrega b | — |

Checklist:

- [x] Todos los criterios `[M]` de la entrega a cumplidos con evidencia
- [x] Ciclo TDD completo en cada fila: rojo antes de verde (`rojo/fila-1.txt`, `fila-2.txt`, `fila-3.txt`) y ningún test editado por un desarrollador. Los únicos cambios a pruebas existentes son los cinco literales `22` a `23` de `D-7`, hechos por `tester-backend`, y las docstrings de `F001`
- [x] Suite en verde, con la salida pegada arriba
- [x] Al menos un test de rechazo por regla implicada (TC-05, TC-11, TC-15, TC-16, TC-19)
- [x] Mutación en rutas críticas: `M-4` a `M-8`, `M-11`, `M-14` a `M-17`, todos muertos
- [x] Todas las auditorías `APROBADO` (`auditor-arquitectura`, `auditor-sql`, `auditor-codigo`); sin `REQUIERE CAMBIOS` pendiente
- [x] Sin hallazgo crítico o mayor pendiente
- [ ] Documentación afectada actualizada en este mismo cambio: pendiente de la entrega b (fila F7: `docs/03` §10, §9 y §14, `docs/07`, `docs/05`, `docs/04` y glosario). `auditor-docs` se ejecuta en la revisión de la entrega b
- [x] `ruff`, `mypy`, `lint-imports` limpios
- [x] Rama `tkt-029b-baja-proveedores` y sin secretos en el diff

`docs/api/openapi.yaml` queda modificado en esta entrega (`DAR_BAJA` al final de `AccionBitacora`); se señala a la persona que aprueba el PR.
