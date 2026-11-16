# Impl · TKT-029b · Baja protegida de proveedores

> [← index](_index.md) | [← design](design.md) | Siguiente: [delta →](delta.md)

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
| `backend/tests/test_tkt007_dominio.py` (`:434`), `test_tkt007_dominio_consulta.py` (docstring), `test_tkt007_esquema.py` (`:262`, `:268`, `:543`), `test_tkt007_fronteras.py` (`:247`) | modificados: `22` pasa a `23` (decisión `D-7`) | pruebas |

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

## Entrega b · baja de proveedores, contrato y documentación (F4 a F7)

### Qué se implementó

La entrega b construye la baja protegida sobre la base de la entrega a. El dominio de `proveedores` decide si un proveedor admite la baja (`RechazoBaja` y `rechazo_de_baja`: `BAJA` es terminal y precede a todo, y cualquier orden pendiente la impide). El caso de uso `dar_baja_proveedor` toma el proveedor con `FOR UPDATE`, lee sus órdenes pendientes por la interfaz publicada de `compras`, aplica la regla, pasa el proveedor a `BAJA` y asienta `DAR_BAJA` en la misma transacción; con órdenes pendientes responde `409` `CONFLICTO` `PROVEEDOR_CON_ORDENES_ABIERTAS` con las órdenes por folio y ofrece desactivar solo si el proveedor está `ACTIVO`. La ruta `POST /api/v1/proveedores/{proveedor_id}/baja` expone el caso de uso con sesión, CSRF y rol `COMPRAS`. El borrador OpenAPI, los tipos del cliente y la documentación quedan al día, y a petición de la persona dueña se añadieron el ADR de la decisión `D-3` y la pregunta abierta `PA-24`.

### Ajustes respecto al design

| Fecha | Cambio | Motivo |
|---|---|---|
| 2026-11-15 | El diccionario de entradas válidas de `test_tkt057_csrf.py` se llama `CUERPOS_VALIDOS`, no `PETICIONES_VALIDAS`; la entrada de `/baja` se añadió ahí | El diseño usó un nombre que no es el del archivo |
| 2026-11-15 | El diff de `test_tkt029a_api_proveedores.py` incluye tres líneas de la docstring del módulo, además de TC-38 y TC-40 | La docstring decía que `/baja` no se publicaba y TC-40 lo exigía; la objeción 11 del diseño pide corregirla junto con esos dos tests |
| 2026-11-15 | Una prueba parametrizada extra de singular y plural del mensaje (`1 orden pendiente` desde `ACTIVO`, `2 órdenes pendientes` desde `DESACTIVADO`) en `test_tkt029b_casos_de_uso.py` | TC-25 solo probaba el plural en `ACTIVO` y TC-26 solo el singular en `DESACTIVADO`: sin ella, un intercambio de ramas no caía |
| 2026-11-15 | TC-42 no distingue el mutante `M-9`; lo mata TC-30. Se corrigieron la docstring de TC-42 y la fila `M-9` del diseño | La lectura sin `FOR UPDATE` no espera, pero el `UPDATE` posterior sí espera y vence el mismo `lock_timeout`, con la misma respuesta observable |
| 2026-11-15 | En el borrador, `desactivar_proveedor` conserva `x-tickets: [TKT-029]` y `x-escenarios: ['HDU-004 esc. 12']`; solo cambia su descripción | El agente de la fila F6 los había cambiado de más; el diseño (`D-11`) solo pide la descripción |
| 2026-11-16 | Se añadieron el ADR `docs/adr/20261116-verbo-dar-baja-y-bajada-recreando-el-tipo.md` (decisión `D-3`) y la pregunta abierta `PA-24` (reactivación y RFC de un proveedor en `BAJA`), con los conteos de ADR (44 a 45) y de preguntas (23 a 24) | La persona dueña lo aprobó tras los hallazgos `F001` y `F006` de `auditor-docs`. El diseño decía «sin ADR» |
| 2026-11-16 | El escenario 12 de HDU-004 dice que el rechazo ofrece desactivar solo si el proveedor está `ACTIVO`, y que desde `DESACTIVADO` no ofrece nada; la regla «una orden sin renglones es `CERRADA`» y la baja terminal y sin liberar el RFC llevan la marca `(asumido)` | Hallazgos `F007`, `F008` y `F009` de la reauditoría de documentación |
| 2026-11-16 | `llms.txt` pasa de 164 a 165 escenarios, y README y `llms.txt` de 69 a 73 tickets | Cifras que `verificar_docs` no comprueba; la de escenarios consecuencia del escenario 13, la de tickets un error previo |

### Archivos tocados

| Archivo | Acción | Capa |
|---|---|---|
| `backend/cimenta/proveedores/dominio/proveedor.py` | modificado (`RechazoBaja`, `rechazo_de_baja`) | dominio |
| `backend/cimenta/proveedores/aplicacion/proveedores.py` | modificado (`dar_baja_proveedor`, `MENSAJE_YA_DADO_DE_BAJA`, `_texto_ordenes`, `_rechazo_ordenes_pendientes`) | aplicación |
| `backend/cimenta/proveedores/api/rutas.py` | modificado (ruta `dar_baja_proveedor`) | api |
| `docs/api/openapi.yaml` | modificado (`dar_baja_proveedor` y descripción de `desactivar_proveedor`, `D-11`) | contrato |
| `frontend/src/api/generado/servidor.ts` | regenerado | contrato |
| `backend/tests/test_tkt029b_dominio_baja.py`, `test_tkt029b_casos_de_uso.py`, `test_tkt029b_api_baja.py` | nuevos | pruebas |
| `backend/tests/test_tkt029a_api_proveedores.py` (TC-38, TC-40 y docstrings) y `test_tkt057_csrf.py` (entrada de `/baja`) | modificados (`D-10`) | pruebas |
| `docs/03-modelo-datos.md`, `docs/07-especificacion-api.md`, `docs/05-tickets-trabajo.md`, `docs/04-historias-usuario.md`, `docs/06-stack-tecnologico.md`, `docs/02-arquitectura.md`, `docs/glosario.md`, `docs/01-descripcion-producto.md`, `README.md`, `llms.txt`, `CLAUDE.md` (solo el conteo de ADR) | modificados | documentación |
| `docs/adr/20261116-verbo-dar-baja-y-bajada-recreando-el-tipo.md` y `docs/adr/README.md` | nuevo y modificado | documentación |

### Pruebas

| # | Test (resumen) | Tipo | Criterio | Antes del código | Al cerrar |
|---|---|---|---|---|---|
| TC-20 a TC-22 | `test_hdu004_esc12_dominio_baja_*` y `dominio_ordenes_pendientes_*` (3 tests) | feliz y **rechazo** | `CA-1` a `CA-4`, `CA-7` | FALLA (`AttributeError`) | PASA |
| TC-23, TC-24 | `test_hdu004_esc13_baja_desde_activo…` y `…desde_desactivado…` | feliz | `CA-1`, `CA-2` | FALLA | PASA |
| TC-25 a TC-28 | `test_hdu004_esc12_baja_con_ordenes_pendientes…`, `…de_desactivado_con_orden_parcial…`, `…ya_dado_de_baja…`, `…inexistente` y la prueba de singular y plural | **rechazo** | `CA-3`, `CA-4`, `CA-7`, `CA-10` | FALLA | PASA |
| TC-29, TC-30 | `test_hdu004_esc13_baja_bitacora_en_la_misma_transaccion` y `test_hdu004_esc12_dos_bajas_concurrentes` | **rechazo** · transacción y concurrencia | `CA-1`, `CA-11` | FALLA | PASA |
| TC-31 a TC-46 | `test_tkt029b_api_baja.py` (38 tests, incluidos los seis casos de `CA-5`, la secuencia de `CA-6`, los 422, los 403 y 401, los dos bloqueos vencidos y el contrato publicado) | feliz y **rechazo** | `CA-1` a `CA-11`, `CA-13`, `CA-14` | FALLA (ruta `404`; borrador con `x-tickets: [TKT-029]`) | PASA |
| TC-47, TC-48 | TC-38 y TC-40 de TKT-029a; entrada de `/baja` en `test_tkt057_csrf.py` | regresión | `CA-R3`, `CA-R4` | FALLA (TC-47); TC-48 nace en verde por diseño | PASA |

### Ciclo TDD por fila

| Fila | Rojo (archivo) | Resultado del rojo | Verde | Modelo |
|---|---|---|---|---|
| F4 | `rojo/fila-4.txt` | `3 failed`, 0 errores; `AttributeError` por `rechazo_de_baja` ausente | `6 passed` (con TKT-029a); `lint-imports` 16 kept; `verificar_float` 0 | `haiku` |
| F5 | `rojo/fila-5.txt` | `10 failed`, 0 errores; `AttributeError` por `dar_baja_proveedor` ausente | `32 passed` (con TKT-029a); `mypy` limpio | `sonnet` (concurrencia) |
| F6 | `rojo/fila-6.txt` | `40 failed, 184 passed`, 0 errores; ruta `404` y borrador sin cambiar | `523 passed` en los siete archivos; tipos regenerados y verificados | `sonnet` (permisos y `409` por HTTP) |
| F7 | Diagramas antes: 30; después: 31 | `extraer_mermaid` encuentra el diagrama «Proveedor» | `verificar_docs` sin problemas; `518` pruebas de `tools/` | `haiku` |

El rojo de las filas F4 a F6 se escribió importando el módulo y leyendo los símbolos nuevos como atributos dentro de cada test, para que el fallo sea de comportamiento y no un error de colección. Con el código ya en verde, el ciclo de corrección sustituyó ese recurso por importaciones normales de cabecera (`F003` de `auditor-codigo`).

### Mutación en rutas críticas

Copia previa de los dos archivos de producción fuera del repositorio, huella SHA-256 de los 354 `.py` de `backend/` antes y después de cada mutante (`56e81a5fff2f8b7f86b99b256cb7be26e5d5aa965b81466c98323f2c868fd4d6`, idéntica en los 16 pasos) y restauración tras cada uno.

| Mutante | Cambio | Test que cae |
|---|---|---|
| `M-1` | `DESACTIVADO` tratado como terminal | `…dominio_baja_sin_ordenes_pendientes_no_se_rechaza`, `…dominio_ordenes_pendientes_impiden_la_baja`, `…baja_desde_desactivado_asienta_el_estado_anterior_real` y dos más (5 caen) |
| `M-2` | `BAJA` deja pasar | `…dominio_baja_es_estado_terminal`, `…baja_de_un_proveedor_ya_dado_de_baja_es_terminal`, `…dos_bajas_concurrentes` y, por HTTP, la baja de un proveedor en `BAJA` |
| `M-3` | `ordenes_pendientes > 0` pasa a `> 1` | `…dominio_ordenes_pendientes_impiden_la_baja`, el singular de la prueba de singular y plural, y por HTTP los casos de un renglón sin recibir y de renglón parcial |
| `M-9` | `leer_proveedor(…, para_cambio=False)` | `…dos_bajas_concurrentes` (TC-30). TC-42 no lo distingue (ajuste registrado arriba) |
| `M-10` | `DESACTIVAR_PROVEEDOR` se ofrece siempre | `…cuenta_en_singular_y_plural[desactivado_dos_ordenes]`, `…baja_de_desactivado_con_orden_parcial_se_rechaza_sin_acciones` y, por HTTP, TC-34 y TC-36 |
| `M-12` | `asentar` con una sesión propia | `…baja_bitacora_en_la_misma_transaccion` (TC-29) |
| `M-13` | `datos_antes` con el literal `ACTIVO` | `…baja_desde_desactivado_asienta_el_estado_anterior_real` |

Los mutantes `M-4` a `M-8`, `M-11` y `M-14` a `M-17` se mataron en la entrega a. `auditor-arquitectura` repitió por su cuenta `M-1`, `M-2`, `M-3`, `M-9`, `M-10` y `M-13`, y todos cayeron. `M-12` lo cubre TC-29 y se aplicó en la corrida de mutación del cierre.

### Modelo por paso

| Paso | Agente | Modelo previsto | Modelo usado | Motivo del cambio |
|---|---|---|---|---|
| F4 · rojo | `tester-backend` | `haiku` | `sonnet` | El rojo se escribe sobre símbolos aún inexistentes y exige cuidado con la colección; el orquestador lo subió |
| F4 · verde | `desarrollador-dominio` | `haiku` | `haiku` | — |
| F5 · rojo | `tester-backend` | `haiku` | `sonnet` | Concurrencia y contrato de error completo |
| F5 · verde | `desarrollador-aplicacion` | `sonnet` | `sonnet` | Disparador del diseño: bloqueo pesimista y dos bajas simultáneas |
| F6 · rojo | `tester-api` | `sonnet` | `sonnet` | — |
| F6 · verde | `desarrollador-api` | `sonnet` | `sonnet` | Disparador del diseño: permisos de un rol y `409` de concurrencia por HTTP |
| F7 | `desarrollador-api` (documentación) | `haiku` | `haiku` | — |
| Cierre: mutación | `tester-backend` | `sonnet` | `sonnet` | — |
| Correcciones | `corrector-revision` | `haiku` | `haiku` | Dos ciclos, todos Menores y redacción |
| ADR y `PA-24` | agente de propósito general | — | `sonnet` | Trabajo de documentación pedido por la persona dueña tras la auditoría |
| Auditorías | `auditor-arquitectura`, `auditor-codigo`, `auditor-seguridad` | `sonnet` | `sonnet` | — |
| Auditoría de documentación y reauditorías acotadas | `auditor-docs`, `auditor-codigo` | `haiku` | `haiku` | Reauditoría de hallazgos Menores y de redacción |

### Auditorías de la entrega b

| Auditor | Veredicto | Hallazgos | Ciclos |
|---|---|---|---|
| `auditor-arquitectura` | `APROBADO` | Tres observaciones sin bloqueo (`O-1` a `O-3`) | 1 |
| `auditor-seguridad` | `APROBADO` | Tres observaciones bajas (`O1` a `O3`): consulta de órdenes sin tope ni índice (`D-9`), carrera con la emisión hasta TKT-030 (`D-5`), y la lista del `409` si `COMPRAS` se limita por obra | 1 |
| `auditor-codigo` | `APROBADO CON MENORES RESUELTOS SIN REAUDITAR` | `F001` a `F005`, `F009`, `N001` resueltos; `N002` rechazado como desviación; `N003` y `N004` aceptadas | 3 (primera pasada, reauditoría y ciclo 2 acotado) |
| `auditor-docs` | `APROBADO CON MENORES RESUELTOS SIN REAUDITAR` | `F001` (ADR) y `F006` (`PA-24`) resueltos con aprobación de la persona dueña; `F002` a `F005` y `F007` a `F009` resueltos | 3 |

**`auditor-codigo`.** Primera pasada `REQUIERE CAMBIOS` con cinco Menores: `F001` (los dos `if` de `dar_baja_proveedor` no cerraban de forma exhaustiva; ahora es un `match` con `assert_never`), `F002` (docstrings), `F003` (importaciones dinámicas del rojo en dos archivos de pruebas), `F004` (dos casos de `422` que se comparaban contra su propia respuesta) y `F005` (TC-35 mezclaba éxito y rechazo en una función). La reauditoría dio por resueltos `F001`, `F004` y `F005` y añadió `N001` y `N002`. Tras el ciclo 2 de `corrector-revision`, los Menores restantes (`F002`, `F003`, `F009`, `N001`) y la frase residual de una docstring se resolvieron sin una tercera reauditoría, con el texto literal del auditor, y se comunican a la persona dueña, según el paso 4 de `/sdd-revisar`.

**`N002`, rechazado.** El auditor pidió renombrar once tests que no llevan el escenario en el nombre. El diseño aprobado fija `test_tkt029b_…` para los criterios que no tienen escenario en la historia (`CA-9` a `CA-12`, `CA-14`, `CA-R1` a `CA-R4`), y esos once son de esa clase; para `CA-10` y `CA-14` además la spec no numera un escenario y su número sería una decisión de la persona dueña. Queda como desviación señalada.

**`N003` y `N004`, aceptadas.** El tipo `Any` en dobles de prueba y en ayudas de cuerpos JSON, y el `# ruff: noqa: F811` a nivel de archivo (que el pipeline acepta y que copia la solución de TKT-029a), son observaciones de estilo sin efecto en el comportamiento.

**`auditor-docs`.** Primera pasada `REQUIERE CAMBIOS`: `F001` Mayor (la decisión `D-3` tiene alternativas descartadas y merece un ADR), `F002` a `F005` (residuos de cifras y referencias) y `F006` (la reactivación del proveedor no estaba registrada como pregunta abierta). La persona dueña aprobó escribir el ADR y registrar `PA-24`. La reauditoría dio esos dos por resueltos y añadió tres Mayores de redacción (`F007` a `F009`: el escenario 12 de la historia no condicionaba la acción de desactivar, y dos supuestos sin la marca `(asumido)`), que se aplicaron en el ciclo 2 con el texto literal del auditor y quedaron verificados con `verificar_docs`.

**Qué verificó `auditor-seguridad`:** orden de dependencias de la ruta (sesión, CSRF, rol), sin oráculo de existencia; IDOR por obra no aplica (catálogo global, sin asignación de usuario a obra); validación del motivo (`NUL`, longitud, sustitutos Unicode); el `409` publica solo `id`, `folio` y `estado`; los errores del motor no se filtran (`55P03` y `57014` traducidos, el resto es un `500` genérico); consultas de `select()` con parámetros enlazados; la bitácora se asienta en la misma transacción; sin secretos ni dependencias nuevas.

**Qué verificó `auditor-arquitectura`:** las 17 reglas de `CLAUDE.md` una por una, `lint-imports` (16 contratos, 0 rotos), `verificar_float`, `mypy`, `ruff`, la mutación repetida sobre una copia fuera del repositorio, y que la regla de la baja sale de HDU-004 esc. 12, `D-6` y las decisiones del 2026-11-15, sin un `RN-xx` inventado. Observación `O-1`: que la persona dueña acepte el escenario 13 y la precedencia de `BAJA` sobre las órdenes, que consta en la aprobación de `D-6` del hub.

### Hallazgos fuera de alcance

| Archivo | Observación | Prioridad |
|---|---|---|
| `docs/05-tickets-trabajo.md` (TKT-030) | La carrera entre emitir una orden y dar de baja al proveedor queda abierta hasta que exista la emisión; TKT-030 lee el proveedor con `FOR SHARE` (`D-5`, viñeta `Should`) | Baja, de TKT-030 |
| `docs/08-wireframes.md` | El boceto del catálogo de proveedores sigue sin reflejar la baja protegida | Baja, de TKT-032 |
| `repositorio_orden_compra.py` | La consulta de órdenes no tiene índice por `proveedor_id` ni tope; con el volumen de la fase 1 no es explotable | Baja, de TKT-032 (`D-9`) |
| `README.md` líneas 39 y 258 | Citan «69 tickets» en prosa fechada el 2026-10-15; son históricas y no se tocan | Ninguna |
| Migración `0016` | Su docstring no enlaza al ADR nuevo; es un archivo de código y no se tocó en esta entrega | Baja |

## Verificación final · entrega b

Corridas del 2026-11-16, con `docker info` respondiendo (servidor 29.9.3), sobre el árbol tras el último ciclo de corrección. Las cifras son las de esa última corrida, que cubre la entrega a y la entrega b acumuladas.

```text
$ uv run pytest                                   (desde backend/, suite completa)
3654 passed, 26 skipped in 722.40s (0:12:02)

$ uv run ruff format --check .
354 files already formatted
$ uv run ruff check .
All checks passed!
$ uv run mypy .
Success: no issues found in 354 source files
$ uv run lint-imports
Contracts: 16 kept, 0 broken.
$ uv run python -m herramientas.verificar_float
verificar_float: archivos revisados: 40; hallazgos: 0
$ python tools/verificar_docs.py                  (desde la raíz)
preguntas 24 · adrs 45 · escenarios 165 · tickets 73 · ✓ Sin problemas.
$ python tools/extraer_mermaid.py
31 diagramas encontrados
$ python -m unittest discover -s tools/tests
Ran 518 tests ... OK
$ npm run tipos:verificar                         (desde frontend/)
Tipos al día.
```

Los 26 `skipped` son las pruebas contra archivos reales de catálogo (`CIMENTA_CATALOGO_*` sin definir, `PA-T3`), que ya existían. Frente a la suite de cierre de la entrega a (`3603 passed`), suman 51 pruebas nuevas de la entrega b (3 de dominio, 10 de casos de uso y 38 de la API). Una primera corrida de la entrega b, antes de los ciclos de corrección, dio `3654 passed, 26 skipped in 685.41s`; la corrida tras el ciclo 1 dio `3654 passed` y esta, tras el ciclo 2, `3654 passed`.

| Criterio | Nivel | Estado | Evidencia |
|---|---|---|---|
| `CA-1` (baja desde `ACTIVO` con motivo, asiento `DAR_BAJA`) | `[M]` | Cumplido | TC-23, TC-29, TC-31 |
| `CA-2` (baja desde `DESACTIVADO`, con su estado anterior real en el asiento) | `[M]` | Cumplido | TC-24, TC-32; mata `M-13` |
| `CA-3` (rechazo `PROVEEDOR_CON_ORDENES_ABIERTAS` desde `ACTIVO`, con órdenes y acción) | `[M]` | Cumplido | TC-25, TC-33; mata `M-3`, `M-11` |
| `CA-4` (rechazo desde `DESACTIVADO`, sin acciones) | `[M]` | Cumplido | TC-26, TC-34; mata `M-10` |
| `CA-5` (qué cuenta como pendiente, seis ejemplos por HTTP) | `[M]` | Cumplido | TC-09 a TC-16 (entrega a), TC-35 |
| `CA-6` (secuencia: baja rechazada, desactivar, baja sigue rechazada) | `[M]` | Cumplido | TC-36; mata `M-10` |
| `CA-7` (desde `BAJA`, `ESTADO_NO_PERMITE_OPERACION`) | `[M]` | Cumplido | TC-21, TC-27, TC-37; mata `M-2` |
| `CA-8` (motivo obligatorio y recortado, `422`) | `[M]` | Cumplido | TC-38 |
| `CA-9` (rol `COMPRAS`, `401`, CSRF) | `[M]` | Cumplido | TC-39, TC-40 y su prueba de apoyo |
| `CA-10` (proveedor inexistente, `404`; id mal formado, `422`) | `[M]` | Cumplido | TC-28, TC-41 |
| `CA-11` (concurrencia: `FOR UPDATE` y dos bloqueos vencidos) | `[M]` | Cumplido | TC-30, TC-42, TC-43; `M-9` lo mata TC-30 |
| `CA-12` (función de lectura de `compras`) | `[M]` | Cumplido (entrega a) | TC-14 a TC-19 |
| `CA-13` (la baja no borra y no libera el RFC) | `[M]` | Cumplido | TC-44, TC-47 |
| `CA-14` (contrato: borrador, `/openapi.json`, verbo en tres lugares) | `[M]` | Cumplido | TC-02, TC-08, TC-45, TC-46; `tipos:verificar` |
| `CA-R1` y `CA-R2` | `[M]` | Cumplido (entrega a) | TC-01 a TC-08, TC-19 |
| `CA-R3` (rutas y operaciones de TKT-029a) | `[M]` | Cumplido | TC-47; suite de TKT-029a en verde |
| `CA-R4` (CSRF y enrutador) | `[M]` | Cumplido | TC-48; `test_tkt057_csrf.py` y `test_tkt006_enrutador.py` en verde |

Checklist:

- [x] Todos los criterios `[M]` del ticket cumplidos con evidencia (los de la entrega a, en su sección)
- [x] Ciclo TDD completo en cada fila: rojo antes de verde (`rojo/fila-4.txt`, `fila-5.txt`, `fila-6.txt`), y ningún test editado por un desarrollador. Los cambios a pruebas existentes (TC-38 y TC-40 de TKT-029a y la entrada de `test_tkt057_csrf.py`) los hizo `tester-api`, citando `D-10`
- [x] Suite en verde, con la salida pegada arriba
- [x] Al menos un test de rechazo por regla implicada (TC-21, TC-22, TC-25 a TC-28, TC-33, TC-34, TC-37 a TC-43)
- [x] Mutación en rutas críticas: `M-1`, `M-2`, `M-3`, `M-9`, `M-10`, `M-12` y `M-13` muertos; `M-9` por TC-30
- [x] Todas las auditorías `APROBADO` o `APROBADO CON MENORES RESUELTOS SIN REAUDITAR`, con la nota del paso 4 de `/sdd-revisar` más arriba
- [x] Sin hallazgo crítico o mayor pendiente; `N002` (Mayor de `auditor-codigo`) queda rechazado como desviación con su motivo, a la espera de que la persona dueña lo confirme al aprobar el PR
- [x] Documentación afectada actualizada en este mismo cambio, con el ADR y `PA-24` aprobados por la persona dueña
- [x] `ruff`, `mypy`, `lint-imports` limpios
- [x] Rama `tkt-029b-baja-proveedores` y sin secretos en el diff

Se verifica en `/sdd-completar`: los nueve trabajos de `ci.yml` y «Etiqueta de origen» en verde sobre el PR real, y la validación de sintaxis de los diagramas Mermaid con el parser del pipeline (aquí `extraer_mermaid.py` solo extrae y no valida). `docs/api/openapi.yaml` queda modificado en las dos entregas (`DAR_BAJA` y la operación de la baja); se señala a la persona que aprueba el PR.
